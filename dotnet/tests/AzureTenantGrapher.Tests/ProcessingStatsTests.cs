using AzureTenantGrapher.Processing;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class ProcessingStatsTests
    {
        [Fact]
        public void DefaultValues_AreZero()
        {
            var stats = new ProcessingStats();
            Assert.Equal(0, stats.TotalResources);
            Assert.Equal(0, stats.Processed);
            Assert.Equal(0, stats.Successful);
            Assert.Equal(0, stats.Failed);
            Assert.Equal(0, stats.LlmGenerated);
        }

        [Fact]
        public void ProcessingStats_CalculatesCorrectly()
        {
            var stats = new ProcessingStats
            {
                TotalResources = 10,
                Processed = 10,
                Successful = 8,
                Failed = 2,
                LlmGenerated = 5
            };
            Assert.Equal(80, stats.Successful * 100 / stats.Processed);
            Assert.Equal(100, stats.Processed * 100 / stats.TotalResources);
        }
    }
}
