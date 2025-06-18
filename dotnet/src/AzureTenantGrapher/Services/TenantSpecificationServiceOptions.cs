namespace AzureTenantGrapher.Services
{
    public class TenantSpecificationServiceOptions
    {
        public bool IncludeTags { get; set; } = true;
        public bool IncludeLocations { get; set; } = true;
        // Add more flags as needed in future
    }
}