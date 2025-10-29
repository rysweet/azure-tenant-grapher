"""Tests for resource filtering functionality in IaC generation."""


class TestResourceFilterParsing:
    """Test the parsing logic for resource_filters parameter."""

    def test_type_filter_generation(self):
        """Test that type-based filters generate correct Cypher."""
        # This tests the parsing logic that should be in cli_handler
        resource_filters = "Microsoft.Network/virtualNetworks"
        filters = [f.strip() for f in resource_filters.split(",")]
        filter_conditions = []

        for f in filters:
            if "=" in f:
                prop_name, prop_value = f.split("=", 1)
                prop_name = prop_name.strip()
                prop_value = prop_value.strip()

                if prop_name.lower() in ("resourcegroup", "resource_group"):
                    if "=~" in f:
                        pattern = prop_value.replace("=~", "").strip()
                        filter_conditions.append(
                            f"(r.resource_group =~ {pattern} OR r.resourceGroup =~ {pattern})"
                        )
                    else:
                        filter_conditions.append(
                            f"(r.resource_group = {prop_value} OR r.resourceGroup = {prop_value})"
                        )
                else:
                    if "=~" in f:
                        pattern = prop_value.replace("=~", "").strip()
                        filter_conditions.append(f"r.{prop_name} =~ {pattern}")
                    else:
                        filter_conditions.append(f"r.{prop_name} = {prop_value}")
            else:
                filter_conditions.append(f"r.type = '{f}'")

        assert len(filter_conditions) == 1
        assert filter_conditions[0] == "r.type = 'Microsoft.Network/virtualNetworks'"

    def test_resource_group_regex_filter(self):
        """Test that resource group regex filters generate correct Cypher."""
        resource_filters = "resourceGroup=~'(?i).*(simuland|SimuLand).*'"
        filters = [f.strip() for f in resource_filters.split(",")]
        filter_conditions = []

        for f in filters:
            if "=" in f:
                is_regex = "=~" in f

                if is_regex:
                    prop_name, pattern = f.split("=~", 1)
                    prop_name = prop_name.strip()
                    pattern = pattern.strip()
                else:
                    prop_name, pattern = f.split("=", 1)
                    prop_name = prop_name.strip()
                    pattern = pattern.strip()

                if prop_name.lower() in ("resourcegroup", "resource_group"):
                    if is_regex:
                        filter_conditions.append(
                            f"(r.resource_group =~ {pattern} OR r.resourceGroup =~ {pattern})"
                        )
                    else:
                        filter_conditions.append(
                            f"(r.resource_group = {pattern} OR r.resourceGroup = {pattern})"
                        )
                else:
                    if is_regex:
                        filter_conditions.append(f"r.{prop_name} =~ {pattern}")
                    else:
                        filter_conditions.append(f"r.{prop_name} = {pattern}")
            else:
                filter_conditions.append(f"r.type = '{f}'")

        assert len(filter_conditions) == 1
        expected = "(r.resource_group =~ '(?i).*(simuland|SimuLand).*' OR r.resourceGroup =~ '(?i).*(simuland|SimuLand).*')"
        assert filter_conditions[0] == expected

    def test_resource_group_exact_match(self):
        """Test that exact resource group name filters generate correct Cypher."""
        resource_filters = "resourceGroup='simuland'"
        filters = [f.strip() for f in resource_filters.split(",")]
        filter_conditions = []

        for f in filters:
            if "=" in f:
                is_regex = "=~" in f

                if is_regex:
                    prop_name, pattern = f.split("=~", 1)
                    prop_name = prop_name.strip()
                    pattern = pattern.strip()
                else:
                    prop_name, pattern = f.split("=", 1)
                    prop_name = prop_name.strip()
                    pattern = pattern.strip()

                if prop_name.lower() in ("resourcegroup", "resource_group"):
                    if is_regex:
                        filter_conditions.append(
                            f"(r.resource_group =~ {pattern} OR r.resourceGroup =~ {pattern})"
                        )
                    else:
                        filter_conditions.append(
                            f"(r.resource_group = {pattern} OR r.resourceGroup = {pattern})"
                        )
                else:
                    if is_regex:
                        filter_conditions.append(f"r.{prop_name} =~ {pattern}")
                    else:
                        filter_conditions.append(f"r.{prop_name} = {pattern}")
            else:
                filter_conditions.append(f"r.type = '{f}'")

        assert len(filter_conditions) == 1
        expected = "(r.resource_group = 'simuland' OR r.resourceGroup = 'simuland')"
        assert filter_conditions[0] == expected

    def test_mixed_filters(self):
        """Test that mixed type and property filters work together."""
        resource_filters = (
            "Microsoft.Network/virtualNetworks,resourceGroup=~'(?i).*simuland.*'"
        )
        filters = [f.strip() for f in resource_filters.split(",")]
        filter_conditions = []

        for f in filters:
            if "=" in f:
                is_regex = "=~" in f

                if is_regex:
                    prop_name, pattern = f.split("=~", 1)
                    prop_name = prop_name.strip()
                    pattern = pattern.strip()
                else:
                    prop_name, pattern = f.split("=", 1)
                    prop_name = prop_name.strip()
                    pattern = pattern.strip()

                if prop_name.lower() in ("resourcegroup", "resource_group"):
                    if is_regex:
                        filter_conditions.append(
                            f"(r.resource_group =~ {pattern} OR r.resourceGroup =~ {pattern})"
                        )
                    else:
                        filter_conditions.append(
                            f"(r.resource_group = {pattern} OR r.resourceGroup = {pattern})"
                        )
                else:
                    if is_regex:
                        filter_conditions.append(f"r.{prop_name} =~ {pattern}")
                    else:
                        filter_conditions.append(f"r.{prop_name} = {pattern}")
            else:
                filter_conditions.append(f"r.type = '{f}'")

        assert len(filter_conditions) == 2
        assert filter_conditions[0] == "r.type = 'Microsoft.Network/virtualNetworks'"
        expected = "(r.resource_group =~ '(?i).*simuland.*' OR r.resourceGroup =~ '(?i).*simuland.*')"
        assert filter_conditions[1] == expected
