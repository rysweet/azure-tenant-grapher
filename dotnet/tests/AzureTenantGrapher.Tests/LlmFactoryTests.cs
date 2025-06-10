using System;
using AzureTenantGrapher.Llm;
using AzureTenantGrapher.Config;
using Xunit;

namespace AzureTenantGrapher.Tests
{
    public class LlmFactoryTests
    {
        [Fact]
        public void Create_WithNullConfig_ReturnsNull()
        {
            var gen = LlmFactory.Create(null);
            Assert.Null(gen);
        }

        [Fact]
        public void Create_WithValidConfig_ReturnsGenerator()
        {
            var config = new AzureOpenAIConfig(
                "https://endpoint/", "key123", "2025-04-16", "chatModel", "reasonModel");
            var gen = LlmFactory.Create(config);
            Assert.NotNull(gen);
        }
    }
}
