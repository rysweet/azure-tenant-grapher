using System;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using AzureTenantGrapher.Core;
using Microsoft.Extensions.Logging;

namespace AzureTenantGrapher.Graph
{
    public class GraphVisualizer
    {
        private readonly string _uri;
        private readonly string _username;
        private readonly string _password;
        private readonly ILogger<GraphVisualizer> _logger;

        public GraphVisualizer(string uri, string username, string password, ILogger<GraphVisualizer> logger)
        {
            _uri = uri;
            _username = username;
            _password = password;
            _logger = logger;
        }

        public async Task GenerateHtmlVisualizationAsync(string outputPath, TenantSpecification spec)
        {
            _logger.LogInformation("Generating HTML visualization at {OutputPath}", outputPath);

            var sb = new StringBuilder();
            sb.AppendLine("<!DOCTYPE html>");
            sb.AppendLine("<html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Tenant Graph Visualization</title></head><body>");
            sb.AppendLine($"<h1>Tenant: {spec.TenantId}</h1>");
            sb.AppendLine($"<p>Generated: {spec.GeneratedOnUtc:u}</p>");
            sb.AppendLine($"<h2>Subscriptions ({spec.Subscriptions.Count})</h2>");
            sb.AppendLine("<table border=\"1\"><tr><th>Subscription ID</th><th>Display Name</th></tr>");
            foreach (var sub in spec.Subscriptions)
            {
                sb.AppendLine($"<tr><td>{System.Net.WebUtility.HtmlEncode(sub.SubscriptionId)}</td><td>{System.Net.WebUtility.HtmlEncode(sub.DisplayName)}</td></tr>");
            }
            sb.AppendLine("</table>");

            sb.AppendLine($"<h2>Resources ({spec.Resources.Count})</h2>");
            sb.AppendLine("<table border=\"1\"><tr><th>Resource ID</th><th>Type</th><th>Location</th></tr>");
            foreach (var res in spec.Resources)
            {
                sb.AppendLine($"<tr><td>{System.Net.WebUtility.HtmlEncode(res.ResourceId)}</td><td>{System.Net.WebUtility.HtmlEncode(res.ResourceType)}</td><td>{System.Net.WebUtility.HtmlEncode(res.Location ?? "")}</td></tr>");
            }
            sb.AppendLine("</table>");
            sb.AppendLine("</body></html>");

            try
            {
                await File.WriteAllTextAsync(outputPath, sb.ToString(), Encoding.UTF8);
                _logger.LogInformation("HTML visualization written successfully.");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to write HTML visualization to {OutputPath}", outputPath);
                throw;
            }
        }
    }
}