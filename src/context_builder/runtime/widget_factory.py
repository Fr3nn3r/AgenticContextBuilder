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
import streamlit as st


class WidgetFactory:
    """
    Factory for creating Streamlit widgets based on field definitions.

    This class is the core of the dynamic form generation system.
    It reads field metadata from the schema and creates appropriate UI components.
    """

    @staticmethod
    def create_widget(
        field_def: Dict[str, Any],
        session_state_key: str,
        current_value: Any = None
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
                field_def, session_state_key, current_value
            )

        # Create widget based on type
        if field_type == "boolean":
            return st.checkbox(
                label,
                value=current_value if current_value is not None else False,
                key=session_state_key
            )

        elif field_type == "enum":
            options = field_def.get("options", [])
            if not options:
                st.warning(f"No options defined for enum field: {label}")
                return None

            # Add a "Select..." placeholder option
            display_options = ["(Select...)"] + options

            # Determine index based on current value
            if current_value and current_value in options:
                index = options.index(current_value) + 1  # +1 for placeholder
            else:
                index = 0  # Placeholder

            selected = st.selectbox(
                label,
                options=display_options,
                index=index,
                key=session_state_key
            )

            # Return None if placeholder is selected
            return None if selected == "(Select...)" else selected

        elif field_type == "integer":
            return st.number_input(
                label,
                value=current_value if current_value is not None else 0,
                step=1,
                format="%d",
                key=session_state_key
            )

        elif field_type == "number":
            return st.number_input(
                label,
                value=current_value if current_value is not None else 0.0,
                step=0.01,
                format="%.2f",
                key=session_state_key
            )

        elif field_type == "string":
            return st.text_input(
                label,
                value=current_value if current_value is not None else "",
                key=session_state_key
            )

        else:
            st.warning(f"Unknown field type '{field_type}' for field: {label}")
            return st.text_input(label, value="", key=session_state_key)

    @staticmethod
    def _create_repeatable_widget(
        field_def: Dict[str, Any],
        session_state_key: str,
        current_value: Any = None
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
                    item_value
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
    flat_state: Dict[str, Any]
) -> None:
    """
    Render an entire section of fields.

    Args:
        section_name: Name of the section (e.g., "header", "incident")
        section_data: Section data from schema
        flat_state: Flat state dictionary to populate with values
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
                current_value=current_value
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
