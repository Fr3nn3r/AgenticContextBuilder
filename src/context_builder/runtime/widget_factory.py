"""
Widget Factory - Part of Component 1 (Dynamic Form Generator).

Implements Abstract Factory Pattern to create UI widgets based on field definitions.

SOLID Principle: Open/Closed Principle (OCP)
Open for new field types (via JSON schema updates), closed for modification.

Type Mappings:
- boolean -> st.checkbox()
- enum -> st.selectbox()
- string -> st.text_input()
- integer -> st.number_input(step=1)
- number -> st.number_input(step=0.01)
- repeatable=true -> container with Add/Remove buttons
"""

from typing import Any, Dict
from datetime import date
import streamlit as st


class WidgetFactory:
    """
    Factory for creating Streamlit widgets based on field definitions.

    This class is the core of the dynamic form generation system.
    It reads field metadata from the schema and creates appropriate UI components.

    Semantic Inference: Uses keyword heuristics to render smart widgets
    beyond just type (boolean, string, number).
    """

    @staticmethod
    def _detect_semantic_type(ui_key: str, field_type: str) -> str:
        """
        Detect semantic type of a field based on its key name.

        This enables rendering smart widgets (currency input, date picker, etc.)
        instead of generic text/number inputs.

        Args:
            ui_key: The ui_key or key name (e.g., "claim_amount", "incident_date")
            field_type: The JSON schema type (string, number, integer, boolean, enum)

        Returns:
            Semantic category: "currency", "date", "duration", "percentage",
                              "long_text", "length", "country", "phone", "email",
                              "short_code", or "default"
        """
        ui_key_lower = ui_key.lower()

        # Currency (money amounts)
        if field_type in ("integer", "number"):
            if any(kw in ui_key_lower for kw in ["amount", "cost", "premium", "benefit", "value", "price", "fee", "payment"]):
                return "currency"

            # Duration (time periods)
            if any(kw in ui_key_lower for kw in ["hours", "days", "duration", "period", "term"]):
                return "duration"

            # Percentage
            if any(kw in ui_key_lower for kw in ["percentage", "percent", "rate", "ratio"]):
                return "percentage"

            # Length/Distance
            if any(kw in ui_key_lower for kw in ["length", "distance", "height", "width", "depth", "meters", "feet"]):
                return "length"

        # Date fields
        if field_type == "string":
            # Exclude description fields from date detection
            if "description" not in ui_key_lower:
                if any(kw in ui_key_lower for kw in ["date", "_at", "time", "when", "effective"]):
                    return "date"

            # Long text fields
            if any(kw in ui_key_lower for kw in ["description", "reason", "notes", "comment", "details", "explanation"]):
                return "long_text"

            # Country
            if any(kw in ui_key_lower for kw in ["country", "nation"]):
                return "country"

            # Phone number
            if any(kw in ui_key_lower for kw in ["phone", "telephone", "mobile", "cell"]):
                return "phone"

            # Email
            if any(kw in ui_key_lower for kw in ["email", "e_mail"]):
                return "email"

            # Short codes (ISO, etc.)
            if len(ui_key) <= 4 and not any(kw in ui_key_lower for kw in ["name", "type"]):
                return "short_code"

        return "default"

    @staticmethod
    def _format_date_custom(date_obj: date | None) -> str | None:
        """
        Format a date object to custom format: "29-Nov-2025"

        Args:
            date_obj: Python date object from st.date_input

        Returns:
            Formatted string or None if date_obj is None
        """
        if date_obj is None:
            return None
        return date_obj.strftime("%d-%b-%Y")

    @staticmethod
    def _parse_date_custom(date_str: str | None) -> date | None:
        """
        Parse custom date format "29-Nov-2025" back to date object.

        Args:
            date_str: String in format "29-Nov-2025"

        Returns:
            Python date object or None
        """
        if not date_str:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(date_str, "%d-%b-%Y").date()
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _get_default_value_smart(field_def: Dict[str, Any], schema: Dict[str, Any] | None = None) -> Any:
        """
        Get smart default value for a field based on type and schema metadata.

        Args:
            field_def: Field definition from schema
            schema: Full schema (optional, for extracting min/max values)

        Returns:
            Smart default value or None
        """
        field_type = field_def.get("type", "string")

        # Booleans default to False (clear off state)
        if field_type == "boolean":
            return False

        # Enums default to None (forces user to select)
        if field_type == "enum":
            return None

        # Numbers: use min_value if available, else None
        if field_type in ("integer", "number"):
            # Check if schema has min_value metadata
            min_value = field_def.get("min_value")
            if min_value is not None:
                return min_value
            # Default to None to force input
            return None

        # Strings default to empty string
        if field_type == "string":
            return ""

        return None

    @staticmethod
    def _normalize_key(text: str) -> str:
        """
        Normalize text for matching symbol table entries.

        Converts "Pre-Existing Condition" or "is_pre_existing_condition" to "pre_existing_condition"

        Args:
            text: Text to normalize

        Returns:
            Normalized lowercase text with underscores
        """
        return text.lower().replace('-', '_').replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')

    @staticmethod
    def _find_definition(ui_key: str, symbol_table: Dict[str, Any]) -> str | None:
        """
        Find matching policy definition in symbol table.

        Strategy:
        1. Normalize ui_key (remove 'is_', 'has_', etc. prefixes)
        2. Search defined_terms for matches
        3. Return simplified_meaning if found

        Args:
            ui_key: The field's ui_key (e.g., "is_civil_disorder", "trip_cost")
            symbol_table: Symbol table dictionary with extracted_data

        Returns:
            Definition string or None if not found
        """
        if not symbol_table:
            return None

        # Normalize the ui_key and remove common boolean prefixes
        search_key = WidgetFactory._normalize_key(ui_key)
        search_key = search_key.replace('is_', '').replace('has_', '').replace('was_', '')

        # Search defined terms
        defined_terms = symbol_table.get('extracted_data', {}).get('defined_terms', [])
        for term in defined_terms:
            term_name = term.get('term', '')
            normalized_term = WidgetFactory._normalize_key(term_name)

            # Check for match
            if search_key in normalized_term or normalized_term in search_key:
                # Return simplified meaning or full definition
                return term.get('simplified_meaning') or term.get('definition', '')

        return None

    @staticmethod
    def _find_limit(ui_key: str, symbol_table: Dict[str, Any]) -> str | None:
        """
        Find matching limit/variable in symbol table.

        Args:
            ui_key: The field's ui_key
            symbol_table: Symbol table dictionary

        Returns:
            Formatted limit string (e.g., "$50,000 USD") or None
        """
        if not symbol_table:
            return None

        search_key = WidgetFactory._normalize_key(ui_key)

        # Search explicit variables
        variables = symbol_table.get('extracted_data', {}).get('explicit_variables', [])
        for var in variables:
            var_name = var.get('name', '')
            normalized_var = WidgetFactory._normalize_key(var_name)

            if search_key in normalized_var or normalized_var in search_key:
                value = var.get('value', '')
                unit = var.get('unit', '')
                context = var.get('context', '')

                # Format nicely
                if value and unit:
                    result = f"{value} {unit}"
                elif value:
                    result = str(value)
                else:
                    continue

                if context:
                    result = f"{result} ({context})"

                return result

        return None

    @staticmethod
    def extract_currency_from_policy(schema: Dict[str, Any], logic: Dict[str, Any]) -> str:
        """
        Extract currency code from policy rules or schema metadata.

        Strategy:
        1. Search logic rules for currency mentions (CAD, USD, EUR, etc.)
        2. Check symbol table if available
        3. Check schema metadata
        4. Default to USD

        Args:
            schema: Schema dictionary
            logic: Logic dictionary with rules

        Returns:
            Currency code (CAD, USD, EUR, GBP, CHF, AUD, etc.)
        """
        common_currencies = ["CAD", "USD", "EUR", "GBP", "CHF", "AUD", "JPY", "NZD", "SGD"]

        # Strategy 1: Search logic rules
        rules = logic.get("transpiled_data", {}).get("rules", [])
        for rule in rules:
            # Check reasoning and source_ref for currency mentions
            reasoning = rule.get("reasoning", "")
            source_ref = rule.get("source_ref", "")
            rule_name = rule.get("name", "")

            combined_text = f"{reasoning} {source_ref} {rule_name}".upper()

            for currency in common_currencies:
                if currency in combined_text:
                    return currency

        # Strategy 2: Check schema metadata
        if "currency" in schema:
            return schema.get("currency", "USD").upper()

        # Strategy 3: Default
        return "USD"

    @staticmethod
    def create_widget(
        field_def: Dict[str, Any],
        session_state_key: str,
        current_value: Any = None,
        currency: str = "USD",
        symbol_table: Dict[str, Any] | None = None
    ) -> Any:
        """
        Create a Streamlit widget based on field definition.

        Args:
            field_def: Field definition from schema with keys:
                - key: Full path (e.g., "claim.incident.attributes.watercraft_length")
                - label: Display label
                - type: Field type (boolean, enum, string, integer, number)
                - options: List of options (for enum type)
                - required: Whether field is required
                - repeatable: Whether field can have multiple values
            session_state_key: Key for storing value in st.session_state
            current_value: Current value (default if not in session state)
            currency: Currency code for currency fields
            symbol_table: Symbol table dictionary with policy definitions (optional)

        Returns:
            Widget value (automatically stored in session state)
        """
        field_type = field_def.get("type", "string")

        # Smart label selection: use ui_key if label is generic/unhelpful
        label = field_def.get("label", "")
        ui_key = field_def.get("ui_key", "")

        # Generic labels that should be replaced with ui_key
        generic_labels = [
            "Risk modifiers e.g. 'is_vacant', 'wind_speed'",
            "Policy-specific header tags",
            "Free text",
            "e.g. 'first_party', 'liability'",
            "e.g. 'Property', 'Liability'"
        ]

        # If label is generic or empty, use ui_key (converted to readable format)
        if not label or label in generic_labels:
            if ui_key:
                # Convert snake_case to Title Case (e.g., "is_watercraft_involved" -> "Is Watercraft Involved")
                label = ui_key.replace("_", " ").title()
            else:
                # Fallback to key
                key = field_def.get("key", "Unknown Field")
                # Extract last part of key path
                label = key.split(".")[-1].replace("_", " ").title()

        required = field_def.get("required", False)
        repeatable = field_def.get("repeatable", False)

        # Add required indicator to label
        if required:
            label = f"{label} *"

        # Handle repeatable fields
        if repeatable:
            return WidgetFactory._create_repeatable_widget(
                field_def, session_state_key, current_value, currency, symbol_table
            )

        # Build context-aware help text using symbol table
        help_text = None

        if symbol_table:
            # Priority 1: Look for policy definition
            definition = WidgetFactory._find_definition(ui_key, symbol_table)
            if definition:
                help_text = f"**Policy Definition:** {definition}"

            # Priority 2: Look for limit/variable info
            if not help_text:
                limit_info = WidgetFactory._find_limit(ui_key, symbol_table)
                if limit_info:
                    help_text = f"**Limit:** {limit_info}"

        # Priority 3: Fall back to schema description (if not generic)
        if not help_text:
            description = field_def.get("description", "")
            # Only use description if it's not the same as label and not generic
            if description and description not in generic_labels and description.lower() != label.lower():
                help_text = description

        # Detect semantic type for smart widget selection
        semantic_type = WidgetFactory._detect_semantic_type(ui_key or field_def.get("key", ""), field_type)

        # Get smart default value
        default_value = WidgetFactory._get_default_value_smart(field_def)
        if current_value is not None:
            default_value = current_value

        # === BOOLEAN WIDGETS ===
        if field_type == "boolean":
            return st.toggle(
                label,
                value=default_value if default_value is not None else False,
                key=session_state_key,
                help=help_text
            )

        # === ENUM WIDGETS ===
        elif field_type == "enum":
            options = field_def.get("options", [])
            if not options:
                st.warning(f"No options defined for enum field: {label}")
                return None

            # Add empty placeholder
            display_options = [""] + options

            # Determine index
            if current_value and current_value in options:
                index = options.index(current_value) + 1
            else:
                index = 0

            selected = st.selectbox(
                label,
                options=display_options,
                index=index,
                key=session_state_key,
                help=help_text,
                format_func=lambda x: "Select..." if x == "" else x
            )

            return None if selected == "" else selected

        # === INTEGER/NUMBER WIDGETS (with semantic variants) ===
        elif field_type in ("integer", "number"):
            step = 1 if field_type == "integer" else 0.01
            fmt = "%d" if field_type == "integer" else "%.2f"

            # Currency fields
            if semantic_type == "currency":
                return st.number_input(
                    f"{label} ({currency})",
                    min_value=0.0 if field_type == "number" else 0,
                    value=default_value if default_value is not None else (0.0 if field_type == "number" else 0),
                    step=step,
                    format=fmt,
                    key=session_state_key,
                    help=help_text
                )

            # Duration fields
            elif semantic_type == "duration":
                unit = "hours" if "hour" in ui_key.lower() else ("days" if "day" in ui_key.lower() else "")
                label_with_unit = f"{label} ({unit})" if unit else label
                return st.number_input(
                    label_with_unit,
                    min_value=0,
                    value=default_value if default_value is not None else 0,
                    step=step,
                    format=fmt,
                    key=session_state_key,
                    help=help_text
                )

            # Percentage fields
            elif semantic_type == "percentage":
                return st.slider(
                    label,
                    min_value=0,
                    max_value=100,
                    value=default_value if default_value is not None else 0,
                    step=1,
                    key=session_state_key,
                    help=help_text
                )

            # Length/Distance fields
            elif semantic_type == "length":
                return st.number_input(
                    f"{label} (meters)",
                    min_value=0.0 if field_type == "number" else 0,
                    value=default_value if default_value is not None else (0.0 if field_type == "number" else 0),
                    step=step,
                    format=fmt,
                    key=session_state_key,
                    help=help_text
                )

            # Default number input
            else:
                return st.number_input(
                    label,
                    value=default_value if default_value is not None else (0.0 if field_type == "number" else 0),
                    step=step,
                    format=fmt,
                    key=session_state_key,
                    help=help_text
                )

        # === STRING WIDGETS (with semantic variants) ===
        elif field_type == "string":

            # Date fields
            if semantic_type == "date":
                # Parse existing value if present
                date_value = WidgetFactory._parse_date_custom(current_value) if current_value else None

                date_input = st.date_input(
                    label,
                    value=date_value,
                    key=session_state_key,
                    help=help_text
                )

                # Convert to custom format
                return WidgetFactory._format_date_custom(date_input)

            # Long text fields
            elif semantic_type == "long_text":
                return st.text_area(
                    label,
                    value=current_value if current_value else "",
                    height=100,
                    key=session_state_key,
                    help=help_text
                )

            # Country fields
            elif semantic_type == "country":
                common_countries = ["", "US", "CA", "GB", "DE", "FR", "CH", "AU", "JP", "CN", "IN", "BR", "MX", "IT", "ES", "NL", "SE", "NO", "DK", "FI"]
                index = common_countries.index(current_value) if current_value in common_countries else 0
                return st.selectbox(
                    label,
                    options=common_countries,
                    index=index,
                    key=session_state_key,
                    help=help_text,
                    format_func=lambda x: "Select country..." if x == "" else x
                )

            # Phone fields
            elif semantic_type == "phone":
                return st.text_input(
                    label,
                    value=current_value if current_value else "",
                    placeholder="+1 (555) 123-4567",
                    max_chars=20,
                    key=session_state_key,
                    help=help_text
                )

            # Email fields
            elif semantic_type == "email":
                return st.text_input(
                    label,
                    value=current_value if current_value else "",
                    placeholder="user@example.com",
                    key=session_state_key,
                    help=help_text
                )

            # Short code fields
            elif semantic_type == "short_code":
                return st.text_input(
                    label,
                    value=current_value if current_value else "",
                    max_chars=10,
                    key=session_state_key,
                    help=help_text
                )

            # Default string input
            else:
                return st.text_input(
                    label,
                    value=current_value if current_value else "",
                    key=session_state_key,
                    help=help_text
                )

        else:
            st.warning(f"Unknown field type '{field_type}' for field: {label}")
            return st.text_input(label, value="", key=session_state_key)

    @staticmethod
    def _create_repeatable_widget(
        field_def: Dict[str, Any],
        session_state_key: str,
        current_value: Any = None,
        currency: str = "USD",
        symbol_table: Dict[str, Any] | None = None
    ) -> list[Any]:
        """
        Create a repeatable field (list) with Add/Remove functionality.

        For repeatable fields, we render:
        1. A list of existing items (each with its own widget)
        2. "Add" button to add new items
        3. "Remove" button next to each item

        Args:
            field_def: Field definition from schema
            session_state_key: Base key for session state
            current_value: Current list of values
            currency: Currency code for currency fields
            symbol_table: Symbol table dictionary with policy definitions (optional)

        Returns:
            List of values
        """
        label = field_def.get("label", "Items")
        field_type = field_def.get("type", "string")

        # Initialize list in session state if not present
        list_key = f"{session_state_key}_list"
        if list_key not in st.session_state:
            st.session_state[list_key] = current_value if isinstance(current_value, list) else []

        st.markdown(f"**{label}** (Repeatable)")

        # Display existing items
        items = st.session_state[list_key]
        updated_items = []

        for idx, item_value in enumerate(items):
            col1, col2 = st.columns([4, 1])

            with col1:
                # Create widget for this item
                item_key = f"{session_state_key}[{idx}]"

                # Create a non-repeatable field def for individual items
                item_field_def = {**field_def, "repeatable": False}

                item_widget_value = WidgetFactory.create_widget(
                    item_field_def,
                    item_key,
                    item_value,
                    currency,
                    symbol_table
                )
                updated_items.append(item_widget_value)

            with col2:
                if st.button(f"Remove", key=f"{session_state_key}_remove_{idx}"):
                    # Mark for removal
                    st.session_state[list_key].pop(idx)
                    st.rerun()

        # Add button
        if st.button(f"Add {label}", key=f"{session_state_key}_add"):
            # Add default value based on type
            default_value = WidgetFactory._get_default_value(field_type)
            st.session_state[list_key].append(default_value)
            st.rerun()

        # Update session state with current values
        st.session_state[list_key] = updated_items

        return updated_items

    @staticmethod
    def _get_default_value(field_type: str) -> Any:
        """
        Get default value for a field type.

        Args:
            field_type: Type of field

        Returns:
            Default value appropriate for the type
        """
        defaults = {
            "boolean": False,
            "integer": 0,
            "number": 0.0,
            "string": "",
            "enum": None
        }
        return defaults.get(field_type, None)


def render_section(
    section_name: str,
    section_data: Dict[str, Any],
    flat_state: Dict[str, Any],
    currency: str = "USD",
    symbol_table: Dict[str, Any] | None = None
) -> None:
    """
    Render an entire section of fields (legacy expander-based layout).

    Args:
        section_name: Name of the section (e.g., "header", "incident")
        section_data: Section data from schema
        flat_state: Flat state dictionary to populate with values
        currency: Currency code for currency fields
        symbol_table: Symbol table dictionary with policy definitions (optional)
    """
    section_title = section_data.get("title", section_name.title())
    fields = section_data.get("fields", [])

    with st.expander(section_title, expanded=True):
        for field in fields:
            field_key = field.get("key")
            is_repeatable = field.get("repeatable", False)

            # Get current value from flat_state
            current_value = flat_state.get(field_key)

            # Create widget
            widget_value = WidgetFactory.create_widget(
                field,
                session_state_key=field_key,
                current_value=current_value,
                currency=currency,
                symbol_table=symbol_table
            )

            # Store value in flat_state
            if is_repeatable and isinstance(widget_value, list):
                # For repeatable fields, store each item with indexed key
                # Convert "claim.parties.claimants[].role" to "claim.parties.claimants[0].role", etc.
                base_key = field_key.replace("[]", "")  # Remove empty brackets

                # Clear any existing indexed keys for this field
                keys_to_remove = [k for k in flat_state.keys() if k.startswith(base_key + "[")]
                for k in keys_to_remove:
                    del flat_state[k]

                # Store each item with indexed key
                for idx, item in enumerate(widget_value):
                    indexed_key = f"{base_key}[{idx}]"
                    flat_state[indexed_key] = item
            else:
                # For non-repeatable fields, store normally
                flat_state[field_key] = widget_value


def render_section_tabbed(
    section_name: str,
    section_data: Dict[str, Any],
    flat_state: Dict[str, Any],
    currency: str = "USD",
    symbol_table: Dict[str, Any] | None = None
) -> None:
    """
    Render a section in modern tab layout with 2-column grid.

    Repeatable fields span both columns for clarity.
    This is the PRODUCT MODE rendering (vs debug mode expanders).

    Args:
        section_name: Name of the section (e.g., "header", "incident")
        section_data: Section data from schema
        flat_state: Flat state dictionary to populate with values
        currency: Currency code for currency fields
        symbol_table: Symbol table dictionary with policy definitions (optional)
    """
    section_title = section_data.get("title", section_name.title())
    fields = section_data.get("fields", [])

    # Section header
    st.markdown(f"### {section_title}")

    if not fields:
        st.info("No fields in this section")
        return

    # Separate repeatable and non-repeatable fields
    regular_fields = [f for f in fields if not f.get("repeatable", False)]
    repeatable_fields = [f for f in fields if f.get("repeatable", False)]

    # Render regular fields in 2-column grid
    if regular_fields:
        cols = st.columns(2)
        for idx, field in enumerate(regular_fields):
            with cols[idx % 2]:
                field_key = field.get("key")
                current_value = flat_state.get(field_key)

                # Create widget
                widget_value = WidgetFactory.create_widget(
                    field,
                    session_state_key=field_key,
                    current_value=current_value,
                    currency=currency
                )

                # Store value in flat_state
                flat_state[field_key] = widget_value

    # Render repeatable fields full-width
    if repeatable_fields:
        st.markdown("---")
        for field in repeatable_fields:
            field_key = field.get("key")
            current_value = flat_state.get(field_key)

            # Create widget
            widget_value = WidgetFactory.create_widget(
                field,
                session_state_key=field_key,
                current_value=current_value,
                currency=currency,
                symbol_table=symbol_table
            )

            # Store value in flat_state (repeatable fields return lists)
            if isinstance(widget_value, list):
                # For repeatable fields, store each item with indexed key
                base_key = field_key.replace("[]", "")

                # Clear existing indexed keys
                keys_to_remove = [k for k in flat_state.keys() if k.startswith(base_key + "[")]
                for k in keys_to_remove:
                    del flat_state[k]

                # Store each item with indexed key
                for idx, item in enumerate(widget_value):
                    indexed_key = f"{base_key}[{idx}]"
                    flat_state[indexed_key] = item
            else:
                flat_state[field_key] = widget_value
