"""Dash form for the cosmonaut job."""

from copy import deepcopy
from typing import Any, List, Tuple, Type, get_args

import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html
from pydantic_core import ValidationError


class InputField:
    """Placeholder class for form fields that will be replaced with actual components."""

    def __init__(self, field_name: str):
        """Initialize with field name from Pydantic model."""
        self.field_name = field_name


def flatten_list(nested_list: List[Any]) -> List[str]:
    """Flatten a nested list."""
    flattened: List[Any] = []
    for item in nested_list:
        if isinstance(item, list):
            flattened.extend(flatten_list(item))
        else:
            if not isinstance(item, str):
                continue
            flattened.append(item)
    return flattened


class FormFactory:
    """Factory class to generate a dash form from a Pydantic model."""

    def __init__(self, pymodel: Type[Any], layout: Any, active: bool = True):
        """
        Initialize FormFactory.

        Args:
            pymodel: Pydantic model class to use for field definitions
            layout: Optional. For generate_form(): OrderedDict layout.
                   For process_layout(): Can be any Dash component tree.
            active: Whether form fields are active (editable) or disabled
        """
        self.pymodel = pymodel
        self.layout = deepcopy(layout)
        self.active = active
        self.type_to_component = {
            "email": dbc.Input,
            "text": dbc.Input,
            "float": dbc.Input,
            "integer": dbc.Input,
            "dropdown-checklist": dbc.DropdownMenu,
            "date-picker": dcc.DatePickerRange,
            "checkbox": dbc.Checkbox,
        }
        self.fields_website = self.extract_field_names(layout)

        self.fieldtypes_not_to_validate = [
            "checkbox",
            "dropdown-checklist",
            "date-picker",
        ]
        if self.active:
            self.id_format = "{field_name}"
            self.feedback_id_format = "{field_name}_feedback"
            self.start_date_id_format = "{field_name}_start_date"
            self.end_date_id_format = "{field_name}_end_date"
        else:
            self.id_format = ""
            self.feedback_id_format = ""

    def create_component(self, field_name: Any) -> Any:
        """Create the component."""
        if not isinstance(field_name, str):
            return field_name
        field = self.pymodel.model_fields[field_name]

        field_type = field.json_schema_extra["type"]
        try:
            component_class = self.type_to_component[field_type]
        except KeyError:
            raise ValueError(f"Unkown field_type: {field_type}")

        props = {}

        id_feedback = self.feedback_id_format.format(field_name=field_name)
        id_field = self.id_format.format(field_name=field_name)
        try:
            value = getattr(self.pymodel, field_name)
        except AttributeError:
            value = field.default

        if field_type in ["text", "email"]:
            props["type"] = "text" if field_type == "text" else "email"
            props["id"] = id_field
            props["value"] = value
            props["html_size"] = len(value) + 5
            props["style"] = {"width": "auto"}
            if not self.active:
                props["disabled"] = True
                props["style"].update({"background-color": "#e9ecef"})
        elif field_type in ["float", "integer"]:
            props["type"] = "number"
            props["step"] = 1 if field_type == "integer" else "any"
            props["required"] = True
            props["id"] = id_field
            props["value"] = value
            props["html_size"] = len(str(value)) + 5
            props["style"] = {"width": "auto"}
            if not self.active:
                props["disabled"] = True
                props["style"].update({"background-color": "#e9ecef"})
        elif field_type == "dropdown-checklist":
            props["label"] = field.title
            choices = get_args(get_args(field.annotation)[0])
            options = []
            prefix = "foobar"
            for choice in choices:
                label = choice.replace("_", " ")
                if not label.startswith(prefix):
                    prefix = label.split(" ")[0]
                    if len(options) > 0:
                        previous_label = options[-1]["label"]
                        options[-1]["label"] = [html.Div(previous_label), html.Hr()]
                options.append(
                    {"label": label, "value": choice, "disabled": not self.active}
                )
            checklist_props = {
                "options": options,
                "value": value,
                "id": id_field,
                "inline": False,
                "style": {"max-height": "300px", "overflow-y": "auto"},
                "className": "ms-2",
            }
            props["children"] = [dbc.Checklist(**checklist_props)]
        elif field_type == "date-picker":
            props["id"] = id_field
            props["start_date"] = value[0]
            props["end_date"] = value[1]
            props["initial_visible_month"] = value[1]
            if not self.active:
                props["disabled"] = True
        elif field_type == "checkbox":
            props["id"] = id_field
            props["value"] = value
            props["label"] = field.title
            if not self.active:
                props["disabled"] = True
        else:
            raise ValueError(f"Unknown field type {field_type}")

        if field_type == "checkbox":
            content = [
                component_class(**props),
                dbc.FormText(field.description),
                html.Br(),
                dbc.FormText(
                    "",
                    id=id_feedback,
                    className="text-danger",
                ),
            ]
        elif field_type == "date-picker":
            content = [
                dbc.Label(field.title),
                html.Br(),
                component_class(**props),
                html.Br(),
                dbc.FormText(field.description),
                dbc.FormText(id=id_feedback, className="text-danger"),
            ]
        else:
            content = [
                dbc.Label(field.title),
                component_class(**props),
                dbc.FormText(field.description),
                dbc.FormFeedback(id=id_feedback),
            ]
        return content

    def extract_field_names(self, layout: Any) -> List[str]:
        """
        Extract all field names from InputField instances in a layout tree.

        Args:
            layout: A Dash component tree that may contain InputField placeholders

        Returns:
            List of field names found in the layout
        """
        field_names = []

        # If it's an InputField, extract the field name
        if isinstance(layout, InputField):
            field_names.append(layout.field_name)

        # If it's a Dash component with children, recursively extract from children
        elif hasattr(layout, "children"):
            field_names.extend(self.extract_field_names(layout.children))

        # If it's a list, recursively extract from each item
        elif isinstance(layout, list):
            for item in layout:
                field_names.extend(self.extract_field_names(item))

        # If it's a dict, recursively extract from each value
        elif isinstance(layout, dict):
            for value in layout.values():
                field_names.extend(self.extract_field_names(value))

        return field_names

    def process_layout(self, layout: Any) -> Any:
        """
        Recursively process a Dash layout tree, replacing InputField instances with components.

        Args:
            layout: A Dash component tree that may contain InputField placeholders

        Returns:
            The processed layout with InputField instances replaced by actual form components
        """
        # If it's an InputField, replace with the actual component
        if isinstance(layout, InputField):
            return self.create_component(layout.field_name)

        # If it's a Dash component with children, recursively process children
        if hasattr(layout, "children"):
            processed_children = self.process_layout(layout.children)
            # Create a new instance with processed children
            layout.children = processed_children
            return layout

        # If it's a list, recursively process each item
        if isinstance(layout, list):
            return [self.process_layout(item) for item in layout]

        # If it's a dict, recursively process each value
        if isinstance(layout, dict):
            return {key: self.process_layout(value) for key, value in layout.items()}

        # Otherwise return as-is (strings, numbers, None, etc.)
        return layout

    def generate_form(self) -> List[Any]:
        """Generate the form layout."""
        for group_name, row in self.layout.items():
            card_layout = []
            for field_names in row:
                col = [
                    dbc.Col(
                        self.create_component(field_name),
                    )
                    for field_name in field_names
                ]
                card_layout.append(
                    dbc.Row(
                        col,
                        class_name="m-2",
                    )
                )

            self.form_layout.append(
                dbc.Card(
                    [
                        dbc.CardHeader(group_name, class_name="w-100 text-center fs-4"),
                        dbc.CardBody(card_layout),
                    ],
                    class_name="my-2 d-flex justify-content-center align-items-center",
                )
            )

        return self.form_layout

    def produce_callback_outputs(self) -> dict:
        """Produce the callback outputs."""
        output_dict = {}
        for field_name in self.fields_website:
            field_type = self.pymodel.model_fields[field_name].json_schema_extra["type"]
            id_feedback = self.feedback_id_format.format(field_name=field_name)
            if field_type not in self.fieldtypes_not_to_validate:
                output_dict[f"{field_name}_valid"] = Output(field_name, "valid")
                output_dict[f"{field_name}_invalid"] = Output(field_name, "invalid")
                output_dict[f"{id_feedback}_type"] = Output(id_feedback, "type")
            output_dict[f"{id_feedback}_children"] = Output(id_feedback, "children")

        return output_dict

    def produce_callback_inputs(self, use_state: bool = False) -> dict:
        """Produce the callback inputs."""
        input_dict = {}
        if use_state:
            callback_context = State
        else:
            callback_context = Input

        for field_name in self.fields_website:
            field_type = self.pymodel.model_fields[field_name].json_schema_extra["type"]
            id_field = self.id_format.format(field_name=field_name)
            if field_type == "date-picker":
                id_start_date = self.start_date_id_format.format(field_name=field_name)
                id_end_date = self.end_date_id_format.format(field_name=field_name)
                input_dict[id_start_date] = callback_context(field_name, "start_date")
                input_dict[id_end_date] = callback_context(field_name, "end_date")
            else:
                input_dict[id_field] = callback_context(field_name, "value")

        return input_dict

    def validate_callback(self, form_data: dict) -> Tuple[bool, dict]:
        """Validate the callback."""
        exceptions = {}
        try:
            self.set_model(form_data)
        except ValidationError as e:
            for error in e.errors():
                msg = error["msg"].replace("Value error, ", "")
                locs = error["loc"]
                if len(locs) == 0:
                    # This should be a model validator that manually passed the location
                    locs = error["ctx"]["loc_tuple"]

                for loc in locs:
                    exceptions[loc] = msg

        valid = True if len(exceptions) == 0 else False

        output_dict = {}
        for field_name in self.fields_website:
            field_type = self.pymodel.model_fields[field_name].json_schema_extra["type"]
            id_feedback = self.feedback_id_format.format(field_name=field_name)
            if field_name in exceptions:
                msg = exceptions.pop(field_name)
                if field_type not in self.fieldtypes_not_to_validate:
                    output_dict[f"{field_name}_valid"] = False
                    output_dict[f"{field_name}_invalid"] = True
                    output_dict[f"{id_feedback}_type"] = "invalid"
                output_dict[f"{id_feedback}_children"] = msg
            else:
                if field_type not in self.fieldtypes_not_to_validate:
                    output_dict[f"{field_name}_valid"] = True
                    output_dict[f"{field_name}_invalid"] = False
                    output_dict[f"{id_feedback}_type"] = "valid"
                output_dict[f"{id_feedback}_children"] = ""

        if len(exceptions) > 0:
            raise ValueError(f"Unhandeled form validation errors: {exceptions}")

        return valid, output_dict

    def set_model(self, form_data: dict) -> None:
        """Set the model from the form data."""
        model_dict = {}
        for field_name in self.pymodel.model_fields:
            field_type = self.pymodel.model_fields[field_name].json_schema_extra["type"]
            if field_type == "date-picker":
                id_start_date = self.start_date_id_format.format(field_name=field_name)
                id_end_date = self.end_date_id_format.format(field_name=field_name)
                model_dict[field_name] = [
                    form_data[id_start_date],
                    form_data[id_end_date],
                ]
            else:
                try:
                    model_dict[field_name] = form_data[field_name]
                except KeyError:
                    pass

        # Try to validate the model with the data from the form.
        try:
            # Create an instance just for validation (don't store it)
            self.pymodel(**model_dict)
        except ValidationError as e:
            # If there are any validation errors, we need to set default values for any
            # missing or invalid fields. Otherwise, there will be a mismatch between the
            # form and the model. If a field is invalid and the user continues to edit
            # the form, any subsequent edits will not be reflected in the model.
            for error in e.errors():
                locs = error["loc"]
                if len(locs) == 0:
                    # This should be a model validator that manually passed the location
                    locs = error["ctx"]["loc_tuple"]

                field = locs[0]
                if field in self.pymodel.model_fields:
                    default = self.pymodel.model_fields[field].default
                    model_dict[field] = default
            # Try again with defaults filled in
            self.pymodel(**model_dict)
            raise
