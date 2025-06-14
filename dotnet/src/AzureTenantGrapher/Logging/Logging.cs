using System;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.DependencyInjection;

namespace AzureTenantGrapher.Logging
{
    public static class Logging
    {
        private static ILoggerFactory? _loggerFactory;
        public static void SetupLogging(Config.LoggingConfig config)
        {
            var serviceCollection = new ServiceCollection()
                .AddLogging(builder =>
                {
                    builder.ClearProviders();
                    builder.SetMinimumLevel(Enum.Parse<LogLevel>(config.LogLevel, true));
                    if (!string.IsNullOrEmpty(config.LogFile))
                    {
                        builder.AddFile(config.LogFile);
                    }
                    else
                    {
                        builder.AddConsole();
                    }
                });

            _loggerFactory = serviceCollection.BuildServiceProvider().GetService<ILoggerFactory>();
        }

        public static ILogger<T> CreateLogger<T>()
        {
            return _loggerFactory!.CreateLogger<T>();
        }
    }
}
