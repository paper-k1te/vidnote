using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net.Http;
using System.Net.Sockets;
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

        [STAThread]
        private static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string serverExe = Path.Combine(baseDir, "vidnote-server.exe");
            if (!File.Exists(serverExe))
            {
                MessageBox.Show("找不到 vidnote-server.exe，请把它和本程序放在同一目录。",
                    "vidnote", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            int port = args.Length > 0 ? int.Parse(args[0]) : FreePort();
            string url = "http://127.0.0.1:" + port + "/";

            try
            {
                _server = Process.Start(new ProcessStartInfo
                {
                    FileName = serverExe,
                    Arguments = "serve-ui --port " + port,
                    WorkingDirectory = baseDir,
                    CreateNoWindow = true,
                    UseShellExecute = false,
                });
            }
            catch (Exception ex)
            {
                MessageBox.Show("启动后端失败：" + ex.Message, "vidnote");
                return;
            }

            if (!WaitForServer(url, 20000))
            {
                KillServer();
                MessageBox.Show("后端没有在 20 秒内就绪，界面无法打开。", "vidnote");
                return;
            }

            var form = new Form
            {
                Text = "vidnote",
                Width = 1180,
                Height = 820,
                MinimumSize = new Size(900, 620),
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
                        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                        "vidnote", "webview");
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
