using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

namespace Vidnote
{
    /// <summary>
    /// 单文件入口：把内置的后端、WebView2 库释放到本地缓存，然后启动窗口外壳。
    /// 用户目录里只保留 vidnote-app.exe 一个文件。
    /// </summary>
    internal static class Launcher
    {
        private static readonly string[] Resources =
        {
            "vidnote-app-host.exe",
            "vidnote-server.exe",
            "Microsoft.Web.WebView2.Core.dll",
            "Microsoft.Web.WebView2.WinForms.dll",
            "WebView2Loader.dll",
        };

        [STAThread]
        private static void Main(string[] args)
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string cache = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "vidnote", "runtime");
                for (int i = 0; i < args.Length - 1; i++)
                {
                    if (args[i] == "--cache")
                    {
                        cache = args[i + 1];
                        break;
                    }
                }
                Directory.CreateDirectory(cache);

                // 版本标记变化或文件缺失时才重新释放，避免每次启动搬 160 MB。
                string buildId = ReadResourceText("build-id.txt").Trim();
                string idFile = Path.Combine(cache, "build-id.txt");
                bool stale = !File.Exists(idFile)
                    || File.ReadAllText(idFile).Trim() != buildId;
                foreach (string name in Resources)
                {
                    if (!File.Exists(Path.Combine(cache, name)))
                    {
                        stale = true;
                        break;
                    }
                }
                if (stale)
                {
                    foreach (string name in Resources)
                    {
                        Extract(name, cache, true);
                    }
                    File.WriteAllText(idFile, buildId);
                }

                string host = Path.Combine(cache, "vidnote-app-host.exe");
                string temp = Path.Combine(Path.GetDirectoryName(cache), "temp");
                var startInfo = new ProcessStartInfo
                {
                    FileName = host,
                    Arguments = "--workdir \"" + baseDir + "\" --temp \"" + temp + "\"",
                    WorkingDirectory = baseDir,
                    UseShellExecute = false,
                };
                Process.Start(startInfo);
            }
            catch (Exception ex)
            {
                try
                {
                    string log = Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                        "vidnote", "launcher.log");
                    File.AppendAllText(
                        log,
                        DateTime.Now.ToString("s") + " " + ex + Environment.NewLine);
                }
                catch
                {
                    // 日志写不进去时仍然弹窗。
                }
                MessageBox.Show("启动 vidnote 失败：" + ex.Message, "vidnote",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private static void Extract(string name, string folder, bool overwrite)
        {
            string target = Path.Combine(folder, name);
            using (Stream source =
                   Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
            {
                if (source == null)
                {
                    throw new FileNotFoundException("缺少内置资源：" + name);
                }
                if (!overwrite && File.Exists(target)
                    && new FileInfo(target).Length == source.Length)
                {
                    return;
                }

                string temporary = target + "." + Process.GetCurrentProcess().Id + ".tmp";
                using (FileStream output = File.Create(temporary))
                {
                    source.CopyTo(output);
                }
                if (File.Exists(target))
                {
                    File.Delete(target);
                }
                File.Move(temporary, target);
            }
        }

        private static string ReadResourceText(string name)
        {
            using (Stream source =
                   Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
            {
                if (source == null)
                {
                    throw new FileNotFoundException("缺少内置资源：" + name);
                }
                using (StreamReader reader = new StreamReader(source))
                {
                    return reader.ReadToEnd();
                }
            }
        }
    }
}
