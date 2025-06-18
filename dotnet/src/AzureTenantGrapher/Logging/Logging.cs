using System;
using Microsoft.Extensions.Logging;

namespace AzureTenantGrapher.Logging
{
    public static class Logging
    {
        public static ILoggerFactory CreateLoggerFactory(LogLevel logLevel = LogLevel.Information)
        {
            return LoggerFactory.Create(builder =>
            {
                builder
                    .ClearProviders()
                    .AddConsole(options =>
                    {
                        options.TimestampFormat = "[HH:mm:ss] ";
                        options.IncludeScopes = false;
                    })
                    .SetMinimumLevel(logLevel);
            });
        }
    }
}