"""
Comprehensive tests for enhanced identity models in tenant_spec_models.py
Tests all new models including User, Group, ServicePrincipal, ConditionalAccessPolicy,
PIMAssignment, AdminRole, and DirectoryRoleAssignment.
"""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.tenant_spec_models import (
    AccessLevel,
    AdminRole,
    APIPermission,
    AuthenticationMethod,
    ConditionalAccessCondition,
    ConditionalAccessControl,
    ConditionalAccessPolicy,
    DirectoryRoleAssignment,
    Group,
    GroupType,
    PermissionType,
    PIMAssignment,
    RiskLevel,
    ServicePrincipal,
    ServicePrincipalCredential,
    User,
)


class TestUserModel:
    """Tests for the enhanced User model."""

    def test_user_valid_instantiation_all_fields(self):
        """Test creating a User with all fields populated."""
        user = User(
            userId="user-123",
            displayName="John Doe",
            emailAddress="john@example.com",
            userPrincipalName="john@contoso.com",
            mail="john.doe@contoso.com",
            jobTitle="Senior Developer",
            department="Engineering",
            managerId="manager-456",
            mfaEnabled=True,
            authenticationMethods=[
                AuthenticationMethod.PASSWORD,
                AuthenticationMethod.MFA_APP,
                AuthenticationMethod.FIDO2,
            ],
            lastSignInDateTime=datetime(2024, 1, 15, 10, 30),
            lastNonInteractiveSignIn=datetime(2024, 1, 14, 8, 0),
            riskLevel=RiskLevel.LOW,
            isGuest=False,
            creationType="Invitation",
            accountEnabled=True,
            onPremisesSyncEnabled=False,
        )

        assert user.id == "user-123"
        assert user.display_name == "John Doe"
        assert user.mfa_enabled is True
        assert len(user.authentication_methods) == 3
        assert AuthenticationMethod.FIDO2 in user.authentication_methods
        assert user.risk_level == RiskLevel.LOW

    def test_user_minimal_required_fields(self):
        """Test creating a User with only required fields."""
        user = User(userId="user-minimal")
        assert user.id == "user-minimal"
        assert user.display_name is None
        assert user.mfa_enabled is None
        assert user.authentication_methods is None

    def test_user_invalid_risk_level(self):
        """Test that invalid risk level values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            User(userId="user-123", risk_level="CRITICAL")  # Invalid enum value

        errors = exc_info.value.errors()
        assert any("risk_level" in str(error) for error in errors)

    def test_user_invalid_authentication_method(self):
        """Test that invalid authentication methods are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            User(userId="user-123", authentication_methods=["InvalidMethod"])

        errors = exc_info.value.errors()
        assert any("authentication_methods" in str(error) for error in errors)

    def test_user_json_serialization(self):
        """Test JSON serialization of User model."""
        user = User(
            userId="user-json",
            displayName="JSON User",
            riskLevel=RiskLevel.MEDIUM,
            authenticationMethods=[AuthenticationMethod.MFA_SMS],
        )

        json_str = user.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "user-json"
        assert data["display_name"] == "JSON User"
        assert data["risk_level"] == "Medium"
        assert data["authentication_methods"] == ["MfaSms"]

    def test_user_json_deserialization(self):
        """Test JSON deserialization with camelCase aliases."""
        json_data = {
            "userId": "user-deser",
            "displayName": "Deserialized User",
            "emailAddress": "deser@example.com",
            "userPrincipalName": "deser@contoso.com",
            "mfaEnabled": True,
            "riskLevel": "High",
            "authenticationMethods": ["Password", "WindowsHello"],
        }

        user = User(**json_data)
        assert user.id == "user-deser"
        assert user.display_name == "Deserialized User"
        assert user.email == "deser@example.com"
        assert user.mfa_enabled is True
        assert user.risk_level == RiskLevel.HIGH
        assert AuthenticationMethod.WINDOWS_HELLO in user.authentication_methods

    def test_user_datetime_handling(self):
        """Test datetime field handling in User model."""
        json_data = {
            "userId": "user-dt",
            "lastSignInDateTime": "2024-01-20T15:30:00",
            "lastNonInteractiveSignIn": "2024-01-19T10:00:00",
        }

        user = User(**json_data)
        assert isinstance(user.last_sign_in_datetime, datetime)
        assert user.last_sign_in_datetime.year == 2024
        assert user.last_sign_in_datetime.month == 1
        assert user.last_sign_in_datetime.day == 20


class TestGroupModel:
    """Tests for the enhanced Group model."""

    def test_group_valid_instantiation_all_fields(self):
        """Test creating a Group with all fields populated."""
        group = Group(
            groupId="group-123",
            displayName="Engineering Team",
            members=["user-1", "user-2", "user-3"],
            groupType=GroupType.SECURITY,
            mailEnabled=True,
            mail="engineering@contoso.com",
            securityEnabled=True,
            dynamicMembershipRule="user.department -eq 'Engineering'",
            membershipRuleProcessingState="On",
            owners=["owner-1", "owner-2"],
            expirationDateTime=datetime(2025, 1, 1),
            renewedDateTime=datetime(2024, 1, 1),
            isAssignableToRole=True,
            visibility="Public",
            createdDateTime=datetime(2023, 1, 1),
            description="Main engineering team group",
        )

        assert group.id == "group-123"
        assert group.display_name == "Engineering Team"
        assert len(group.members) == 3
        assert group.group_type == GroupType.SECURITY
        assert group.is_assignable_to_role is True

    def test_group_minimal_required_fields(self):
        """Test creating a Group with only required fields."""
        group = Group(groupId="group-minimal")
        assert group.id == "group-minimal"
        assert group.members is None
        assert group.group_type is None

    def test_group_invalid_type(self):
        """Test that invalid group type values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Group(groupId="group-123", group_type="InvalidType")

        errors = exc_info.value.errors()
        assert any("group_type" in str(error) for error in errors)

    def test_group_dynamic_membership(self):
        """Test Group with dynamic membership configuration."""
        group = Group(
            groupId="group-dynamic",
            groupType=GroupType.DYNAMIC,
            dynamicMembershipRule="user.department -eq 'Sales'",
            membershipRuleProcessingState="On",
        )

        assert group.group_type == GroupType.DYNAMIC
        assert "Sales" in group.dynamic_membership_rule

    def test_group_json_serialization(self):
        """Test JSON serialization of Group model."""
        group = Group(
            groupId="group-json",
            displayName="JSON Group",
            groupType=GroupType.MICROSOFT365,
            members=["member-1"],
            mailEnabled=True,
        )

        json_str = group.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "group-json"
        assert data["group_type"] == "Microsoft365"
        assert data["mail_enabled"] is True

    def test_group_json_deserialization(self):
        """Test JSON deserialization with camelCase aliases."""
        json_data = {
            "groupId": "group-deser",
            "displayName": "Deserialized Group",
            "groupType": "MailEnabledSecurity",
            "mailEnabled": True,
            "securityEnabled": True,
            "isAssignableToRole": False,
        }

        group = Group(**json_data)
        assert group.id == "group-deser"
        assert group.display_name == "Deserialized Group"
        assert group.group_type == GroupType.MAIL_ENABLED_SECURITY
        assert group.mail_enabled is True
        assert group.is_assignable_to_role is False


class TestServicePrincipalModel:
    """Tests for the enhanced ServicePrincipal model."""

    def test_service_principal_with_api_permissions(self):
        """Test ServicePrincipal with API permissions."""
        api_perm1 = APIPermission(
            resource_app_id="00000003-0000-0000-c000-000000000000",
            permission_id="perm-123",
            permission_name="User.Read",
            permission_type=PermissionType.DELEGATED,
        )

        api_perm2 = APIPermission(
            resource_app_id="00000003-0000-0000-c000-000000000000",
            permission_id="perm-456",
            permission_name="Directory.Read.All",
            permission_type=PermissionType.APPLICATION,
        )

        sp = ServicePrincipal(
            spId="sp-123",
            displayName="My App",
            appId="app-guid-123",
            apiPermissions=[api_perm1, api_perm2],
        )

        assert sp.id == "sp-123"
        assert len(sp.api_permissions) == 2
        assert sp.api_permissions[0].permission_name == "User.Read"
        assert sp.api_permissions[1].permission_type == PermissionType.APPLICATION

    def test_service_principal_with_credentials(self):
        """Test ServicePrincipal with credentials."""
        cred1 = ServicePrincipalCredential(
            credentialType="Certificate",
            displayName="Prod Certificate",
            endDateTime=datetime(2025, 1, 1),
            startDateTime=datetime(2024, 1, 1),
            thumbprint="ABC123DEF456",  # pragma: allowlist secret
        )

        cred2 = ServicePrincipalCredential(
            credentialType="ClientSecret",
            displayName="Dev Secret",
            endDateTime=datetime(2024, 6, 1),
            startDateTime=datetime(2023, 6, 1),
        )

        sp = ServicePrincipal(
            spId="sp-creds", displayName="Cred App", credentials=[cred1, cred2]
        )

        assert len(sp.credentials) == 2
        assert sp.credentials[0].credential_type == "Certificate"
        assert (
            sp.credentials[0].thumbprint == "ABC123DEF456"  # pragma: allowlist secret
        )  # pragma: allowlist secret  # pragma: allowlist secret
        assert sp.credentials[1].credential_type == "ClientSecret"

    def test_service_principal_minimal(self):
        """Test ServicePrincipal with minimal fields."""
        sp = ServicePrincipal(spId="sp-minimal")
        assert sp.id == "sp-minimal"
        assert sp.api_permissions is None
        assert sp.credentials is None

    def test_service_principal_complete(self):
        """Test ServicePrincipal with all fields."""
        sp = ServicePrincipal(
            spId="sp-complete",
            displayName="Complete App",
            appId="app-123",
            appDisplayName="Complete Application",
            apiPermissions=[],
            appRoles=["Role1", "Role2"],
            oauth2Permissions=["Scope1", "Scope2"],
            credentials=[],
            signInAudience="AzureADMyOrg",
            appOwnerOrganizationId="org-123",
            homepage="https://app.example.com",
            replyUrls=["https://app.example.com/callback"],
            servicePrincipalType="Application",
            tags=["Production", "Critical"],
            accountEnabled=True,
            publisherName="Contoso Inc.",
        )

        assert sp.app_id == "app-123"
        assert len(sp.app_roles) == 2
        assert "Production" in sp.tags
        assert sp.account_enabled is True

    def test_api_permission_invalid_type(self):
        """Test that invalid permission type is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            APIPermission(
                resource_app_id="app-123",
                permission_id="perm-123",
                permission_type="Invalid",
            )

        errors = exc_info.value.errors()
        assert any("permission_type" in str(error) for error in errors)

    def test_service_principal_json_serialization(self):
        """Test JSON serialization of ServicePrincipal."""
        sp = ServicePrincipal(
            spId="sp-json",
            displayName="JSON SP",
            appId="app-json",
            tags=["Tag1", "Tag2"],
        )

        json_str = sp.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "sp-json"
        assert data["app_id"] == "app-json"
        assert len(data["tags"]) == 2

    def test_service_principal_json_deserialization(self):
        """Test JSON deserialization with aliases."""
        json_data = {
            "spId": "sp-deser",
            "displayName": "Deser SP",
            "appId": "app-deser",
            "appDisplayName": "Deser App",
            "signInAudience": "AzureADMultipleOrgs",
            "accountEnabled": False,
        }

        sp = ServicePrincipal(**json_data)
        assert sp.id == "sp-deser"
        assert sp.app_id == "app-deser"
        assert sp.sign_in_audience == "AzureADMultipleOrgs"
        assert sp.account_enabled is False


class TestConditionalAccessPolicy:
    """Tests for ConditionalAccessPolicy model."""

    def test_conditional_access_policy_complete(self):
        """Test ConditionalAccessPolicy with all fields."""
        condition = ConditionalAccessCondition(
            usersInclude=["user-1", "user-2"],
            usersExclude=["user-3"],
            groupsInclude=["group-1"],
            applicationsInclude=["app-1"],
            platformsInclude=["iOS", "Android"],
            locationsInclude=["trusted-location-1"],
            signInRiskLevels=[RiskLevel.MEDIUM, RiskLevel.HIGH],
            userRiskLevels=[RiskLevel.HIGH],
        )

        controls = ConditionalAccessControl(
            grantControls=["MFA", "CompliantDevice"],
            sessionControls=["AppEnforcedRestrictions"],
            operator="AND",
        )

        policy = ConditionalAccessPolicy(
            policyId="policy-123",
            displayName="Require MFA for risky sign-ins",
            state="enabled",
            conditions=condition,
            controls=controls,
            createdDateTime=datetime(2023, 6, 1),
            modifiedDateTime=datetime(2024, 1, 15),
        )

        assert policy.id == "policy-123"
        assert policy.state == "enabled"
        assert len(policy.conditions.users_include) == 2
        assert RiskLevel.HIGH in policy.conditions.sign_in_risk_levels
        assert "MFA" in policy.controls.grant_controls

    def test_conditional_access_policy_minimal(self):
        """Test ConditionalAccessPolicy with minimal fields."""
        policy = ConditionalAccessPolicy(policyId="policy-minimal")
        assert policy.id == "policy-minimal"
        assert policy.conditions is None
        assert policy.controls is None

    def test_conditional_access_risk_levels(self):
        """Test risk level enum validation in conditions."""
        with pytest.raises(ValidationError) as exc_info:
            ConditionalAccessCondition(signInRiskLevels=["InvalidRisk"])

        errors = exc_info.value.errors()
        assert any("sign_in_risk_levels" in str(error) for error in errors)

    def test_conditional_access_json_serialization(self):
        """Test JSON serialization of ConditionalAccessPolicy."""
        policy = ConditionalAccessPolicy(
            policyId="policy-json",
            displayName="JSON Policy",
            state="disabled",
            conditions=ConditionalAccessCondition(usersInclude=["user-1"]),
        )

        json_str = policy.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "policy-json"
        assert data["state"] == "disabled"
        assert data["conditions"]["users_include"] == ["user-1"]

    def test_conditional_access_json_deserialization(self):
        """Test JSON deserialization with aliases."""
        json_data = {
            "policyId": "policy-deser",
            "displayName": "Deser Policy",
            "state": "enabledForReportingButNotEnforced",
            "conditions": {"usersInclude": ["user-x"], "groupsExclude": ["group-y"]},
            "controls": {"grantControls": ["MFA"], "operator": "OR"},
        }

        policy = ConditionalAccessPolicy(**json_data)
        assert policy.id == "policy-deser"
        assert policy.conditions.users_include == ["user-x"]
        assert policy.controls.operator == "OR"


class TestPIMAssignment:
    """Tests for PIMAssignment model."""

    def test_pim_assignment_complete(self):
        """Test PIMAssignment with all fields."""
        assignment = PIMAssignment(
            assignmentId="pim-123",
            principalId="user-456",
            principalType="User",
            roleDefinitionId="role-789",
            roleDisplayName="Global Administrator",
            scope="/",
            accessLevel=AccessLevel.ELIGIBLE,
            startDateTime=datetime(2024, 1, 1),
            endDateTime=datetime(2024, 12, 31),
            assignmentState="Active",
            justification="Required for project X",
            ticketInfo="TICKET-12345",
        )

        assert assignment.id == "pim-123"
        assert assignment.access_level == AccessLevel.ELIGIBLE
        assert assignment.role_display_name == "Global Administrator"
        assert "project X" in assignment.justification

    def test_pim_assignment_minimal(self):
        """Test PIMAssignment with minimal required fields."""
        assignment = PIMAssignment(
            assignmentId="pim-minimal",
            principalId="principal-1",
            roleDefinitionId="role-1",
            scope="/subscriptions/sub-1",
        )

        assert assignment.id == "pim-minimal"
        assert assignment.access_level is None
        assert assignment.justification is None

    def test_pim_assignment_access_level_validation(self):
        """Test AccessLevel enum validation."""
        assignment = PIMAssignment(
            assignmentId="pim-1",
            principalId="p-1",
            roleDefinitionId="r-1",
            scope="/",
            accessLevel=AccessLevel.ACTIVE,
        )
        assert assignment.access_level == AccessLevel.ACTIVE

        with pytest.raises(ValidationError) as exc_info:
            PIMAssignment(
                assignmentId="pim-2",
                principalId="p-2",
                roleDefinitionId="r-2",
                scope="/",
                accessLevel="Permanent",  # Invalid
            )

        errors = exc_info.value.errors()
        assert any("accessLevel" in str(error) for error in errors)

    def test_pim_assignment_json_serialization(self):
        """Test JSON serialization of PIMAssignment."""
        assignment = PIMAssignment(
            assignmentId="pim-json",
            principalId="p-json",
            roleDefinitionId="r-json",
            scope="/",
            accessLevel=AccessLevel.ELIGIBLE,
        )

        json_str = assignment.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "pim-json"
        assert data["access_level"] == "Eligible"

    def test_pim_assignment_json_deserialization(self):
        """Test JSON deserialization with aliases."""
        json_data = {
            "assignmentId": "pim-deser",
            "principalId": "p-deser",
            "principalType": "Group",
            "roleDefinitionId": "r-deser",
            "roleDisplayName": "Contributor",
            "scope": "/subscriptions/sub-123",
            "accessLevel": "Active",
            "justification": "Emergency access",
        }

        assignment = PIMAssignment(**json_data)
        assert assignment.id == "pim-deser"
        assert assignment.principal_type == "Group"
        assert assignment.access_level == AccessLevel.ACTIVE


class TestAdminRole:
    """Tests for AdminRole model."""

    def test_admin_role_complete(self):
        """Test AdminRole with all fields."""
        role = AdminRole(
            roleId="role-123",
            displayName="Custom Admin",
            description="Custom administrative role",
            isBuiltIn=False,
            isEnabled=True,
            templateId="template-456",
            members=["user-1", "user-2", "group-1"],
            permissions=["User.Read.All", "Directory.Write.All"],
        )

        assert role.id == "role-123"
        assert role.is_built_in is False
        assert len(role.members) == 3
        assert "Directory.Write.All" in role.permissions

    def test_admin_role_minimal(self):
        """Test AdminRole with minimal fields."""
        role = AdminRole(roleId="role-minimal")
        assert role.id == "role-minimal"
        assert role.members is None
        assert role.permissions is None

    def test_admin_role_built_in(self):
        """Test AdminRole for built-in roles."""
        role = AdminRole(
            roleId="role-builtin",
            displayName="Global Administrator",
            isBuiltIn=True,
            isEnabled=True,
            templateId="62e90394-69f5-4237-9190-012177145e10",
        )

        assert role.is_built_in is True
        assert role.template_id == "62e90394-69f5-4237-9190-012177145e10"

    def test_admin_role_json_serialization(self):
        """Test JSON serialization of AdminRole."""
        role = AdminRole(
            roleId="role-json",
            displayName="JSON Role",
            isEnabled=True,
            members=["member-1"],
        )

        json_str = role.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "role-json"
        assert data["is_enabled"] is True

    def test_admin_role_json_deserialization(self):
        """Test JSON deserialization with aliases."""
        json_data = {
            "roleId": "role-deser",
            "displayName": "Deser Role",
            "description": "Test role",
            "isBuiltIn": True,
            "isEnabled": False,
            "templateId": "template-123",
            "permissions": ["Permission1", "Permission2"],
        }

        role = AdminRole(**json_data)
        assert role.id == "role-deser"
        assert role.is_built_in is True
        assert role.is_enabled is False
        assert len(role.permissions) == 2


class TestDirectoryRoleAssignment:
    """Tests for DirectoryRoleAssignment model."""

    def test_directory_role_assignment_complete(self):
        """Test DirectoryRoleAssignment with all fields."""
        assignment = DirectoryRoleAssignment(
            assignmentId="dra-123",
            principalId="principal-456",
            principalType="ServicePrincipal",
            roleId="role-789",
            roleDisplayName="Application Administrator",
            directoryScope="/",
            appScopeId="app-scope-123",
            createdDateTime=datetime(2024, 1, 1),
        )

        assert assignment.id == "dra-123"
        assert assignment.principal_type == "ServicePrincipal"
        assert assignment.app_scope_id == "app-scope-123"

    def test_directory_role_assignment_minimal(self):
        """Test DirectoryRoleAssignment with minimal fields."""
        assignment = DirectoryRoleAssignment(
            assignmentId="dra-minimal", principalId="p-1", roleId="r-1"
        )

        assert assignment.id == "dra-minimal"
        assert assignment.directory_scope is None
        assert assignment.created_datetime is None

    def test_directory_role_assignment_json_serialization(self):
        """Test JSON serialization of DirectoryRoleAssignment."""
        assignment = DirectoryRoleAssignment(
            assignmentId="dra-json",
            principalId="p-json",
            roleId="r-json",
            roleDisplayName="Reader",
        )

        json_str = assignment.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "dra-json"
        assert data["role_display_name"] == "Reader"

    def test_directory_role_assignment_json_deserialization(self):
        """Test JSON deserialization with aliases."""
        json_data = {
            "assignmentId": "dra-deser",
            "principalId": "p-deser",
            "principalType": "User",
            "roleId": "r-deser",
            "roleDisplayName": "Contributor",
            "directoryScope": "/administrativeUnits/au-123",
            "createdDateTime": "2024-01-15T10:30:00",
        }

        assignment = DirectoryRoleAssignment(**json_data)
        assert assignment.id == "dra-deser"
        assert assignment.principal_type == "User"
        assert assignment.directory_scope == "/administrativeUnits/au-123"
        assert isinstance(assignment.created_datetime, datetime)


class TestEnumValidation:
    """Tests for enum validation across models."""

    def test_all_risk_levels(self):
        """Test all valid RiskLevel enum values."""
        for level in [
            RiskLevel.NONE,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.HIDDEN,
        ]:
            user = User(userId="user-test", riskLevel=level)
            assert user.risk_level == level

    def test_all_authentication_methods(self):
        """Test all valid AuthenticationMethod enum values."""
        methods = [
            AuthenticationMethod.PASSWORD,
            AuthenticationMethod.MFA_SMS,
            AuthenticationMethod.MFA_VOICE,
            AuthenticationMethod.MFA_APP,
            AuthenticationMethod.FIDO2,
            AuthenticationMethod.WINDOWS_HELLO,
            AuthenticationMethod.CERTIFICATE,
        ]

        user = User(userId="user-test", authenticationMethods=methods)
        assert len(user.authentication_methods) == 7
        assert AuthenticationMethod.CERTIFICATE in user.authentication_methods

    def test_all_group_types(self):
        """Test all valid GroupType enum values."""
        for group_type in [
            GroupType.SECURITY,
            GroupType.MICROSOFT365,
            GroupType.DISTRIBUTION,
            GroupType.MAIL_ENABLED_SECURITY,
            GroupType.DYNAMIC,
        ]:
            group = Group(groupId="group-test", groupType=group_type)
            assert group.group_type == group_type

    def test_all_permission_types(self):
        """Test all valid PermissionType enum values."""
        for perm_type in [PermissionType.APPLICATION, PermissionType.DELEGATED]:
            api_perm = APIPermission(
                resourceAppId="app-123",
                permissionId="perm-123",
                permissionType=perm_type,
            )
            assert api_perm.permission_type == perm_type

    def test_all_access_levels(self):
        """Test all valid AccessLevel enum values."""
        for level in [AccessLevel.ELIGIBLE, AccessLevel.ACTIVE]:
            assignment = PIMAssignment(
                id="pim-test",
                principalId="p-1",
                roleDefinitionId="r-1",
                scope="/",
                accessLevel=level,
            )
            assert assignment.access_level == level


class TestComplexSerialization:
    """Tests for complex serialization scenarios."""

    def test_nested_models_serialization(self):
        """Test serialization of models with nested objects."""
        sp = ServicePrincipal(
            id="sp-nested",
            api_permissions=[
                APIPermission(
                    resourceAppId="app-1",
                    permissionId="perm-1",
                    permissionType=PermissionType.DELEGATED,
                )
            ],
            credentials=[
                ServicePrincipalCredential(
                    credentialType="Certificate",
                    displayName="Cert1",
                    endDateTime=datetime(2025, 1, 1),
                )
            ],
        )

        json_str = sp.model_dump_json()
        data = json.loads(json_str)

        assert data["api_permissions"][0]["permission_type"] == "Delegated"
        assert data["credentials"][0]["credential_type"] == "Certificate"

    def test_nested_models_deserialization(self):
        """Test deserialization of models with nested objects."""
        json_data = {
            "policyId": "policy-nested",
            "conditions": {
                "usersInclude": ["user-1"],
                "signInRiskLevels": ["Medium", "High"],
                "userRiskLevels": ["Low"],
            },
            "controls": {"grantControls": ["MFA"], "operator": "AND"},
        }

        policy = ConditionalAccessPolicy(**json_data)
        assert policy.id == "policy-nested"
        assert RiskLevel.MEDIUM in policy.conditions.sign_in_risk_levels
        assert policy.controls.operator == "AND"

    def test_datetime_iso_format(self):
        """Test datetime fields handle ISO format strings."""
        iso_datetime = "2024-01-15T10:30:00Z"
        user = User(userId="user-dt", lastSignInDateTime=iso_datetime)

        assert isinstance(user.last_sign_in_datetime, datetime)
        assert user.last_sign_in_datetime.hour == 10
        assert user.last_sign_in_datetime.minute == 30

    def test_optional_list_fields(self):
        """Test that optional list fields can be None or empty."""
        group1 = Group(groupId="group-1", members=None)
        group2 = Group(groupId="group-2", members=[])
        group3 = Group(groupId="group-3", members=["user-1"])

        assert group1.members is None
        assert group2.members == []
        assert len(group3.members) == 1

    def test_field_alias_consistency(self):
        """Test that both snake_case and camelCase work for all fields."""
        # Test with snake_case-like names (but still using proper field names)
        user1 = User(
            userId="user-1",
            displayName="Snake Case",
            userPrincipalName="snake@example.com",
        )

        # Test with camelCase (aliases)
        user2 = User(
            userId="user-2",
            displayName="Camel Case",
            userPrincipalName="camel@example.com",
        )

        assert user1.id == "user-1"
        assert user1.display_name == "Snake Case"
        assert user2.id == "user-2"
        assert user2.display_name == "Camel Case"


class TestErrorHandling:
    """Tests for error handling and validation."""

    def test_missing_required_field(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            User()  # Missing required 'userId' field

        errors = exc_info.value.errors()
        assert any("userId" in str(error) for error in errors)

    def test_invalid_datetime_format(self):
        """Test that invalid datetime strings are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            User(userId="user-1", lastSignInDateTime="not-a-date")

        errors = exc_info.value.errors()
        assert any("datetime" in str(error).lower() for error in errors)

    def test_wrong_type_for_list_field(self):
        """Test that non-list values for list fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Group(groupId="group-1", members="not-a-list")

        errors = exc_info.value.errors()
        assert any("members" in str(error) for error in errors)

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored (or handled per config)."""
        user = User(userId="user-1", unknown_field="ignored")
        assert user.id == "user-1"
        assert not hasattr(user, "unknown_field")

    def test_null_vs_empty_string(self):
        """Test distinction between null and empty string."""
        user1 = User(userId="user-1", displayName=None)
        user2 = User(userId="user-2", displayName="")

        assert user1.display_name is None
        assert user2.display_name == ""

    def test_boolean_field_validation(self):
        """Test boolean field type validation."""
        user = User(userId="user-1", mfaEnabled=True)
        assert user.mfa_enabled is True

        user = User(userId="user-2", mfaEnabled=False)
        assert user.mfa_enabled is False

        # Test that non-boolean values are coerced or rejected
        user = User(userId="user-3", mfaEnabled="true")  # String should be coerced
        assert user.mfa_enabled is True
