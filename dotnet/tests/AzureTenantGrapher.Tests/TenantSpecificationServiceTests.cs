using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using AzureTenantGrapher.Core;
using AzureTenantGrapher.Services;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    using SubscriptionInfo = AzureTenantGrapher.Core.SubscriptionInfo;
    using ResourceInfo = AzureTenantGrapher.Core.ResourceInfo;

    public class TenantSpecificationServiceTests
    {
        private static TenantSpecificationService CreateService(
            TenantSpecificationServiceOptions? options,
            Func<TenantSpecification, TenantSpecification>? postProcessor,
            out Mock<ILogger<TenantSpecificationService>> loggerMock)
        {
            loggerMock = new Mock<ILogger<TenantSpecificationService>>();
            return new TenantSpecificationService(
                options ?? new TenantSpecificationServiceOptions(),
                loggerMock.Object,
                postProcessor
            );
        }

        private static TenantSpecificationService CreateService(out Mock<ILogger<TenantSpecificationService>> loggerMock)
        {
            return CreateService(null, null, out loggerMock);
        }

        [Fact]
        public async Task BuildTenantSpecAsync_ReturnsValidSpec()
        {
            // Arrange
            var subs = new List<SubscriptionInfo>
            {
                new SubscriptionInfo { SubscriptionId = "sub1", DisplayName = "Sub One" }
            };
            var resources = new List<ResourceInfo>
            {
                new ResourceInfo { ResourceId = "res1", ResourceType = "typeA", Location = "westus", Tags = new Dictionary<string, string> { { "env", "prod" } } }
            };
            var options = new TenantSpecificationServiceOptions { IncludeTags = true, IncludeLocations = true };
            var postProcessorMock = new Mock<Func<TenantSpecification, TenantSpecification>>();
            postProcessorMock.Setup(f => f(It.IsAny<TenantSpecification>()))
                .Returns<TenantSpecification>(spec =>
                {
                    spec.Stats.LlmGenerated = 42;
                    return spec;
                });

            var service = CreateService(options, postProcessorMock.Object, out var logger);

            // Act
            var spec = await service.BuildTenantSpecAsync(subs, resources);

            // Assert
            Assert.NotNull(spec);
            Assert.Equal("sub1", spec.TenantId);
            Assert.Single(spec.Subscriptions);
            Assert.Single(spec.Resources);
            Assert.Equal("res1", spec.Resources[0].ResourceId);
            Assert.Equal("typeA", spec.Resources[0].ResourceType);
            Assert.Equal("westus", spec.Resources[0].Location);
            Assert.NotNull(spec.Resources[0].Tags);
            Assert.Equal("prod", spec.Resources[0].Tags["env"]);
            Assert.Equal(42, spec.Stats.LlmGenerated);
            postProcessorMock.Verify(f => f(It.IsAny<TenantSpecification>()), Times.Once);
        }

        [Fact]
        public async Task BuildTenantSpecAsync_HandlesNullOrEmptyInputs()
        {
            var service = CreateService(out var logger);

            // Null subscriptions
            await Assert.ThrowsAsync<ArgumentNullException>(() =>
                service.BuildTenantSpecAsync(null, new List<ResourceInfo>()));

            // Null resources
            await Assert.ThrowsAsync<ArgumentNullException>(() =>
                service.BuildTenantSpecAsync(new List<SubscriptionInfo>(), null));

            // Empty lists
            var spec = await service.BuildTenantSpecAsync(new List<SubscriptionInfo>(), new List<ResourceInfo>());
            Assert.NotNull(spec);
            Assert.Empty(spec.Subscriptions);
            Assert.Empty(spec.Resources);
            Assert.Equal(0, spec.Stats.TotalResources);
        }
    }
}
