"""Test assertion utilities for demo walkthrough."""

import re
from typing import Dict, Any, List, Optional
from playwright.async_api import Page, expect


class TestAssertions:
    """Provides test assertion capabilities for demo scenarios."""

    def __init__(self):
        """Initialize test assertions."""
        self.assertion_types = {
            'element_visible': self._assert_element_visible,
            'element_hidden': self._assert_element_hidden,
            'text_contains': self._assert_text_contains,
            'text_equals': self._assert_text_equals,
            'value_equals': self._assert_value_equals,
            'attribute_equals': self._assert_attribute_equals,
            'url_contains': self._assert_url_contains,
            'title_contains': self._assert_title_contains,
            'element_count': self._assert_element_count,
            'element_enabled': self._assert_element_enabled,
            'element_disabled': self._assert_element_disabled,
            'checkbox_checked': self._assert_checkbox_checked,
            'radio_selected': self._assert_radio_selected,
            'option_selected': self._assert_option_selected,
            'css_property': self._assert_css_property,
            'local_storage': self._assert_local_storage,
            'cookie_exists': self._assert_cookie_exists,
            'network_request': self._assert_network_request,
            'console_message': self._assert_console_message,
            'custom': self._assert_custom
        }
        self.results: List[Dict[str, Any]] = []

    async def run(self, page: Page, assertion: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single assertion.

        Args:
            page: Playwright page object
            assertion: Assertion configuration

        Returns:
            Result dictionary with success status and message
        """
        assertion_type = assertion.get('type')
        if assertion_type not in self.assertion_types:
            return {
                'success': False,
                'message': f"Unknown assertion type: {assertion_type}",
                'assertion': assertion
            }

        try:
            handler = self.assertion_types[assertion_type]
            await handler(page, assertion)
            result = {
                'success': True,
                'message': f"Assertion passed: {assertion_type}",
                'assertion': assertion
            }
        except Exception as e:
            result = {
                'success': False,
                'message': f"Assertion failed: {str(e)}",
                'assertion': assertion,
                'error': str(e)
            }

        self.results.append(result)
        return result

    async def run_multiple(self, page: Page, assertions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run multiple assertions and return all results."""
        results = []
        for assertion in assertions:
            result = await self.run(page, assertion)
            results.append(result)
        return results

    async def _assert_element_visible(self, page: Page, assertion: Dict[str, Any]):
        """Assert that an element is visible."""
        selector = assertion['selector']
        timeout = assertion.get('timeout', 30000)
        await expect(page.locator(selector)).to_be_visible(timeout=timeout)

    async def _assert_element_hidden(self, page: Page, assertion: Dict[str, Any]):
        """Assert that an element is hidden."""
        selector = assertion['selector']
        timeout = assertion.get('timeout', 30000)
        await expect(page.locator(selector)).to_be_hidden(timeout=timeout)

    async def _assert_text_contains(self, page: Page, assertion: Dict[str, Any]):
        """Assert that element text contains a value."""
        selector = assertion['selector']
        value = assertion['value']
        timeout = assertion.get('timeout', 30000)

        if assertion.get('ignore_case', False):
            await expect(page.locator(selector)).to_contain_text(
                value,
                timeout=timeout,
                ignore_case=True
            )
        else:
            await expect(page.locator(selector)).to_contain_text(value, timeout=timeout)

    async def _assert_text_equals(self, page: Page, assertion: Dict[str, Any]):
        """Assert that element text equals a value."""
        selector = assertion['selector']
        value = assertion['value']
        timeout = assertion.get('timeout', 30000)
        await expect(page.locator(selector)).to_have_text(value, timeout=timeout)

    async def _assert_value_equals(self, page: Page, assertion: Dict[str, Any]):
        """Assert that input value equals a value."""
        selector = assertion['selector']
        value = assertion['value']
        timeout = assertion.get('timeout', 30000)
        await expect(page.locator(selector)).to_have_value(value, timeout=timeout)

    async def _assert_attribute_equals(self, page: Page, assertion: Dict[str, Any]):
        """Assert that element attribute equals a value."""
        selector = assertion['selector']
        attribute = assertion['attribute']
        value = assertion['value']
        timeout = assertion.get('timeout', 30000)
        await expect(page.locator(selector)).to_have_attribute(attribute, value, timeout=timeout)

    async def _assert_url_contains(self, page: Page, assertion: Dict[str, Any]):
        """Assert that URL contains a value."""
        value = assertion['value']
        timeout = assertion.get('timeout', 30000)

        if assertion.get('regex', False):
            await expect(page).to_have_url(re.compile(value), timeout=timeout)
        else:
            current_url = page.url
            assert value in current_url, f"URL {current_url} does not contain {value}"

    async def _assert_title_contains(self, page: Page, assertion: Dict[str, Any]):
        """Assert that page title contains a value."""
        value = assertion['value']
        timeout = assertion.get('timeout', 30000)

        if assertion.get('regex', False):
            await expect(page).to_have_title(re.compile(value), timeout=timeout)
        else:
            title = await page.title()
            assert value in title, f"Title '{title}' does not contain '{value}'"

    async def _assert_element_count(self, page: Page, assertion: Dict[str, Any]):
        """Assert the number of elements matching a selector."""
        selector = assertion['selector']
        count = assertion['count']
        timeout = assertion.get('timeout', 30000)
        await expect(page.locator(selector)).to_have_count(count, timeout=timeout)

    async def _assert_element_enabled(self, page: Page, assertion: Dict[str, Any]):
        """Assert that an element is enabled."""
        selector = assertion['selector']
        timeout = assertion.get('timeout', 30000)
        await expect(page.locator(selector)).to_be_enabled(timeout=timeout)

    async def _assert_element_disabled(self, page: Page, assertion: Dict[str, Any]):
        """Assert that an element is disabled."""
        selector = assertion['selector']
        timeout = assertion.get('timeout', 30000)
        await expect(page.locator(selector)).to_be_disabled(timeout=timeout)

    async def _assert_checkbox_checked(self, page: Page, assertion: Dict[str, Any]):
        """Assert that a checkbox is checked."""
        selector = assertion['selector']
        checked = assertion.get('checked', True)
        timeout = assertion.get('timeout', 30000)

        if checked:
            await expect(page.locator(selector)).to_be_checked(timeout=timeout)
        else:
            await expect(page.locator(selector)).not_to_be_checked(timeout=timeout)

    async def _assert_radio_selected(self, page: Page, assertion: Dict[str, Any]):
        """Assert that a radio button is selected."""
        selector = assertion['selector']
        timeout = assertion.get('timeout', 30000)
        await expect(page.locator(selector)).to_be_checked(timeout=timeout)

    async def _assert_option_selected(self, page: Page, assertion: Dict[str, Any]):
        """Assert that a select option is selected."""
        selector = assertion['selector']
        value = assertion['value']

        selected_value = await page.locator(selector).input_value()
        assert selected_value == value, f"Selected value '{selected_value}' does not match expected '{value}'"

    async def _assert_css_property(self, page: Page, assertion: Dict[str, Any]):
        """Assert CSS property value."""
        selector = assertion['selector']
        property_name = assertion['property']
        expected_value = assertion['value']

        actual_value = await page.locator(selector).evaluate(
            f"(element) => window.getComputedStyle(element).getPropertyValue('{property_name}')"
        )
        assert actual_value == expected_value, \
            f"CSS property '{property_name}' value '{actual_value}' does not match expected '{expected_value}'"

    async def _assert_local_storage(self, page: Page, assertion: Dict[str, Any]):
        """Assert local storage value."""
        key = assertion['key']
        expected_value = assertion.get('value')

        actual_value = await page.evaluate(f"() => localStorage.getItem('{key}')")

        if expected_value is None:
            assert actual_value is not None, f"Local storage key '{key}' does not exist"
        else:
            assert actual_value == expected_value, \
                f"Local storage value '{actual_value}' does not match expected '{expected_value}'"

    async def _assert_cookie_exists(self, page: Page, assertion: Dict[str, Any]):
        """Assert that a cookie exists."""
        name = assertion['name']
        cookies = await page.context.cookies()

        cookie_names = [c['name'] for c in cookies]
        assert name in cookie_names, f"Cookie '{name}' does not exist"

        if 'value' in assertion:
            cookie = next((c for c in cookies if c['name'] == name), None)
            assert cookie['value'] == assertion['value'], \
                f"Cookie value '{cookie['value']}' does not match expected '{assertion['value']}'"

    async def _assert_network_request(self, page: Page, assertion: Dict[str, Any]):
        """Assert that a network request was made."""
        url_pattern = assertion['url']
        method = assertion.get('method', 'GET')
        timeout = assertion.get('timeout', 5000)

        # Wait for request matching pattern
        try:
            async with page.expect_request(
                lambda req: url_pattern in req.url and req.method == method,
                timeout=timeout
            ) as request_info:
                request = await request_info.value
                assert request is not None, f"No {method} request to {url_pattern} found"
        except Exception:
            raise AssertionError(f"No {method} request to {url_pattern} found within {timeout}ms")

    async def _assert_console_message(self, page: Page, assertion: Dict[str, Any]):
        """Assert console message presence."""
        message_text = assertion['text']
        message_type = assertion.get('type', 'log')  # log, error, warning, info

        # Collect console messages
        console_messages = []

        def handle_console(msg):
            if msg.type == message_type:
                console_messages.append(msg.text)

        page.on("console", handle_console)

        # Wait a bit for messages to appear
        await page.wait_for_timeout(assertion.get('wait', 1000))

        # Check if message was logged
        found = any(message_text in msg for msg in console_messages)
        assert found, f"Console {message_type} message containing '{message_text}' not found"

    async def _assert_custom(self, page: Page, assertion: Dict[str, Any]):
        """Run custom assertion code."""
        code = assertion['code']
        expected = assertion.get('expected', True)

        result = await page.evaluate(code)
        assert result == expected, f"Custom assertion failed: {code} returned {result}, expected {expected}"

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all assertion results."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        failed = total - passed

        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'results': self.results
        }

    def clear_results(self):
        """Clear stored results."""
        self.results = []

    @staticmethod
    def create_assertion(assertion_type: str, **kwargs) -> Dict[str, Any]:
        """
        Helper method to create assertion configuration.

        Args:
            assertion_type: Type of assertion
            **kwargs: Assertion parameters

        Returns:
            Assertion configuration dictionary
        """
        assertion = {'type': assertion_type}
        assertion.update(kwargs)
        return assertion