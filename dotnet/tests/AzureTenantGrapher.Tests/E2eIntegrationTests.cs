using System;
using System.Diagnostics;
using System.IO;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class E2eIntegrationTests
    {
        [Fact]
        public void ContainerOnlyMode_ShouldExitSuccessfully()
        {
            // Determine project directory based on test assembly location
            var baseDir = AppContext.BaseDirectory;
            // Navigate up to repository root (adjust levels as needed)
            var repoRoot = Path.GetFullPath(Path.Combine(baseDir, "../../../../../../"));
            var projectDir = Path.Combine(repoRoot, "dotnet", "src", "AzureTenantGrapher");

            var startInfo = new ProcessStartInfo
            {
                FileName = "dotnet",
                Arguments = "run -- --containerOnly",
                WorkingDirectory = projectDir,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(startInfo);
            Assert.NotNull(process);

            bool exited = process.WaitForExit(60000);
            Assert.True(exited, "Process did not exit within timeout.");

            var output = process.StandardOutput.ReadToEnd();
            var error = process.StandardError.ReadToEnd();
            Assert.Equal(0, process.ExitCode);
            Assert.Contains("Container-only mode complete", output);
        }
    }
}
