using System;
using System.Collections.Generic;
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
                string requested = null;
                for (int i = 0; i < args.Length - 1; i++)
                {
                    if (args[i] == "--cache")
                    {
                        requested = args[i + 1];
                        break;
                    }
                }
                string cache = FindWritableCache(requested, baseDir);

                // 版本标记变化或文件缺失时才重新释放，避免每次启动搬 100+ MB。
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
                    // 路径末尾的反斜杠会转义引号，先去掉。
                    Arguments = "--workdir \"" + baseDir.TrimEnd('\\')
                        + "\" --temp \"" + temp.TrimEnd('\\') + "\"",
                    WorkingDirectory = baseDir,
                    UseShellExecute = false,
                };
                Process.Start(startInfo);
            }
            catch (Exception ex)
            {
                LogError(ex);
                MessageBox.Show("启动 vidnote 失败：" + ex.Message, "vidnote",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        /// <summary>
        /// 找一个可写的运行时目录：LocalAppData 被 ACL 或安全软件挡住时，
        /// 依次退到 LocalLow、系统临时目录、exe 旁边，避免应用直接起不来。
        /// </summary>
        private static string FindWritableCache(string requested, string baseDir)
        {
            string[] candidates;
            if (!string.IsNullOrEmpty(requested))
            {
                candidates = new[] { requested };
            }
            else
            {
                string profile = Environment.GetFolderPath(
                    Environment.SpecialFolder.UserProfile);
                candidates = new[]
                {
                    Path.Combine(
                        Environment.GetFolderPath(
                            Environment.SpecialFolder.LocalApplicationData),
                        "vidnote", "runtime"),
                    Path.Combine(
                        profile, "AppData", "LocalLow", "vidnote", "runtime"),
                    Path.Combine(Path.GetTempPath(), "vidnote", "runtime"),
                    Path.Combine(baseDir, ".vidnote", "runtime"),
                };
            }

            var failures = new List<string>();
            foreach (string candidate in candidates)
            {
                try
                {
                    Directory.CreateDirectory(candidate);
                    string probe = Path.Combine(candidate, ".write-test");
                    File.WriteAllText(probe, "ok");
                    File.Delete(probe);
                    return candidate;
                }
                catch (Exception ex)
                {
                    failures.Add(candidate + " -> " + ex.Message);
                }
            }
            throw new IOException(
                "没有可写的运行时目录：\r\n" + string.Join("\r\n", failures)
                + "\r\n可以给快捷方式加 --cache \"D:\\vidnote-cache\" 指定一个可写目录。");
        }

        private static void LogError(Exception ex)
        {
            string[] logs =
            {
                Path.Combine(
                    Environment.GetFolderPath(
                        Environment.SpecialFolder.LocalApplicationData),
                    "vidnote", "launcher.log"),
                Path.Combine(Path.GetTempPath(), "vidnote-launcher.log"),
            };
            foreach (string log in logs)
            {
                try
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(log));
                    File.AppendAllText(
                        log,
                        DateTime.Now.ToString("s") + " " + ex + Environment.NewLine);
                    return;
                }
                catch
                {
                    // 换下一个位置。
                }
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
