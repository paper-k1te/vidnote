using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net.Http;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace Vidnote
{
    /// <summary>
    /// vidnote 的桌面外壳：启动本地后端（vidnote-server.exe），等它就绪，
    /// 然后用 WebView2 承载界面。窗口关闭时结束后端进程。
    ///
    /// 编译目标是 .NET Framework 4.8（Windows 自带），所以不需要用户安装运行时。
    /// </summary>
    internal static class Program
    {
        private static Process _server;
        private static Mutex _instance;

        [DllImport("user32.dll")]
        private static extern bool SetProcessDpiAwarenessContext(IntPtr value);

        private static readonly IntPtr PerMonitorAwareV2 = new IntPtr(-4);

        [STAThread]
        private static void Main(string[] args)
        {
            // 高 DPI 屏幕上按物理像素渲染，文字和 WebView2 才不会发虚。
            try
            {
                SetProcessDpiAwarenessContext(PerMonitorAwareV2);
            }
            catch
            {
                // 旧系统不支持时退回清单里的 DPI 设置。
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string workdir = baseDir;
            string serverTemp = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "vidnote", "temp");
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == "--workdir")
                {
                    workdir = args[i + 1];
                }
                else if (args[i] == "--temp")
                {
                    serverTemp = args[i + 1];
                }
            }
            if (!Directory.Exists(workdir))
            {
                workdir = baseDir;
            }

            // 同一时间只允许一个窗口，避免两个进程共用 WebView2 配置目录。
            bool createdNew;
            _instance = new Mutex(true, "vidnote-app-single-instance-2", out createdNew);
            if (!createdNew)
            {
                return;
            }

            string serverExe = Path.Combine(baseDir, "vidnote-server.exe");
            if (!File.Exists(serverExe))
            {
                MessageBox.Show("找不到 vidnote-server.exe，请把它和本程序放在同一目录。",
                    "vidnote", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // 单文件版的运行时在缓存目录里，临时文件单独放，不污染用户选的目录。
            try
            {
                Directory.CreateDirectory(serverTemp);
            }
            catch
            {
                // 受限账户写不了 LocalAppData 时退回程序目录。
                serverTemp = Path.Combine(baseDir, "temp");
                Directory.CreateDirectory(serverTemp);
            }
            foreach (string old in Directory.GetDirectories(serverTemp, "webview-*"))
            {
                try
                {
                    Directory.Delete(old, true);
                }
                catch
                {
                    // 上一次的 WebView2 可能还没完全退出，下次再清。
                }
            }
            foreach (string old in Directory.GetDirectories(serverTemp, "_MEI*"))
            {
                try
                {
                    Directory.Delete(old, true);
                }
                catch
                {
                    // 后端还没退干净时删不掉，下次启动再清。
                }
            }

            int port = 0;
            if (args.Length > 0)
            {
                int.TryParse(args[0], out port);
            }
            if (port <= 0)
            {
                port = FreePort();
            }
            string url = "http://127.0.0.1:" + port + "/";

            try
            {
                var startInfo = new ProcessStartInfo
                {
                    FileName = serverExe,
                    Arguments = "serve-ui --port " + port,
                    WorkingDirectory = workdir,
                    CreateNoWindow = true,
                    UseShellExecute = false,
                };
                startInfo.EnvironmentVariables["TEMP"] = serverTemp;
                startInfo.EnvironmentVariables["TMP"] = serverTemp;
                _server = Process.Start(startInfo);
            }
            catch (Exception ex)
            {
                MessageBox.Show("启动后端失败：" + ex.Message, "vidnote");
                return;
            }

            if (!WaitForServer(url, 60000))
            {
                KillServer();
                MessageBox.Show("后端没有在 60 秒内就绪，界面无法打开。", "vidnote");
                return;
            }

            // 按屏幕缩放把逻辑尺寸换算成物理像素，保证 150% / 200% 下文字不发虚、布局不变窄。
            float scale = 1.0f;
            using (Graphics graphics = Graphics.FromHwnd(IntPtr.Zero))
            {
                scale = graphics.DpiX / 96.0f;
            }
            Rectangle work = Screen.PrimaryScreen.WorkingArea;
            int width = Math.Min((int)(1180 * scale), work.Width - 40);
            int height = Math.Min((int)(820 * scale), work.Height - 40);
            int minWidth = Math.Min((int)(900 * scale), width);
            int minHeight = Math.Min((int)(620 * scale), height);

            var form = new Form
            {
                Text = "vidnote",
                Width = width,
                Height = height,
                MinimumSize = new Size(minWidth, minHeight),
                AutoScaleMode = AutoScaleMode.None,
                StartPosition = FormStartPosition.CenterScreen,
                BackColor = Color.White,
            };

            var web = new WebView2 { Dock = DockStyle.Fill };
            form.Controls.Add(web);
            form.FormClosed += delegate { KillServer(); };

            form.Load += async delegate
            {
                try
                {
                    string profile = Path.Combine(
                        serverTemp, "webview-" + Process.GetCurrentProcess().Id);
                    Directory.CreateDirectory(profile);

                    CoreWebView2Environment environment =
                        await CoreWebView2Environment.CreateAsync(null, profile);
                    await web.EnsureCoreWebView2Async(environment);

                    web.CoreWebView2.Settings.AreDevToolsEnabled = false;
                    web.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
                    web.CoreWebView2.Navigate(url);
                }
                catch (Exception ex)
                {
                    MessageBox.Show("加载界面失败：" + ex.Message, "vidnote");
                    form.Close();
                }
            };

            Application.Run(form);
        }

        private static int FreePort()
        {
            var listener = new TcpListener(System.Net.IPAddress.Loopback, 0);
            listener.Start();
            int port = ((System.Net.IPEndPoint)listener.LocalEndpoint).Port;
            listener.Stop();
            return port;
        }

        private static bool WaitForServer(string url, int timeoutMs)
        {
            using (var client = new HttpClient())
            {
                client.Timeout = TimeSpan.FromSeconds(2);
                var deadline = DateTime.UtcNow.AddMilliseconds(timeoutMs);
                while (DateTime.UtcNow < deadline)
                {
                    try
                    {
                        var response = client.GetAsync(url + "api/health").Result;
                        if (response.IsSuccessStatusCode)
                        {
                            // 读掉响应体再关闭连接，避免后端写响应时遇到连接重置。
                            response.Content.ReadAsStringAsync().Wait();
                            return true;
                        }
                    }
                    catch
                    {
                        // 后端还没起来，继续等
                    }
                    Thread.Sleep(200);
                }
            }
            return false;
        }

        private static void KillServer()
        {
            try
            {
                if (_server != null && !_server.HasExited)
                {
                    _server.Kill();
                    _server.WaitForExit(3000);
                }
            }
            catch
            {
                // 进程可能已经退出
            }
        }
    }
}
