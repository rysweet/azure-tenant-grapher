using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using AzureTenantGrapher.Services;
using AzureTenantGrapher.Processing;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class ResourceProcessingServiceTests
    {
        private static List<ResourceInfo> CreateTestResources(int count)
        {
            return Enumerable.Range(1, count)
                .Select(i => new ResourceInfo(
                    $"resource-{i}",
                    $"Test Resource {i}",
                    "Microsoft.Storage/storageAccounts",
                    "East US",
                    new Dictionary<string, string> { { "env", "test" } },
                    "sub-1",
                    "rg-1"))
                .ToList();
        }

        [Fact]
        public async Task ProcessResourcesAsync_ReturnsCorrectStats()
        {
            // Arrange
            var logger = new Mock<ILogger<ResourceProcessingService>>();
            var options = new ResourceProcessingServiceOptions
            {
                BatchSize = 3,
                MaxDegreeOfParallelism = 2,
                MaxRetries = 2
            };
            var resources = CreateTestResources(10);

            // Processor: succeed for even, fail for odd
            var processor = new Func<ResourceInfo, Task<bool>>(r =>
                Task.FromResult(int.Parse(r.Id.Split('-')[1]) % 2 == 0)
            );

            var service = new ResourceProcessingService(logger.Object, options, processor);

            // Act
            var stats = await service.ProcessResourcesAsync(resources);

            // Assert
            Assert.Equal(10, stats.TotalResources);
            Assert.Equal(10, stats.Processed);
            Assert.Equal(5, stats.Successful);
            Assert.Equal(5, stats.Failed);
            Assert.InRange(stats.LlmGenerated, 0, 10); // LlmGenerated is random
        }

        [Fact]
        public async Task ProcessResourcesAsync_RetriesAndFailsGracefully()
        {
            // Arrange
            var logger = new Mock<ILogger<ResourceProcessingService>>();
            var options = new ResourceProcessingServiceOptions
            {
                BatchSize = 2,
                MaxDegreeOfParallelism = 1,
                MaxRetries = 3
            };
            var resources = CreateTestResources(4);

            // Processor: fail first 2 attempts, succeed on 3rd for resource-1, always fail for resource-2
            var callCounts = new Dictionary<string, int>();
            Task<bool> Processor(ResourceInfo r)
            {
                if (!callCounts.ContainsKey(r.Id))
                    callCounts[r.Id] = 0;
                callCounts[r.Id]++;
                if (r.Id == "resource-1" && callCounts[r.Id] < 3)
                    throw new Exception("Simulated failure");
                if (r.Id == "resource-1")
                    return Task.FromResult(true);
                return Task.FromResult(false);
            }

            var service = new ResourceProcessingService(logger.Object, options, Processor);

            // Act
            var stats = await service.ProcessResourcesAsync(resources);

            // Assert
            Assert.Equal(4, stats.TotalResources);
            Assert.Equal(4, stats.Processed);
            Assert.Equal(1, stats.Successful);
            Assert.Equal(3, stats.Failed);
        }
    }
}
