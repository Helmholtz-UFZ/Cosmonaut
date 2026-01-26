# Error Handling Conventions

## Central Error Handler

All error handling is centralized in `cosmonaut_app/error_handling.py`.

---

## Adding New Errors

1. **Define custom exception class** in `error_handling.py`:
   ```python
   class MyCustomError(Exception):
       def __init__(self, some_id):
           self.some_id = some_id
           super().__init__(f"Error with {some_id}")
   ```

2. **Add to `error_responds_dict`** with user-friendly message:
   ```python
   error_responds_dict = {
       MyCustomError: ("Error Title", "User-friendly message about {some_id}"),
       # ...
   }
   ```

3. **Decide on admin notification** - should error send email to admin?

---

## Existing Custom Exceptions

- `JobNotFound(job_id)` - Job not in database
- `WrongCeleryTaskId(task_id)` - Invalid Celery task ID

---

## Error Modal

User-facing errors display in modal dialog:
- `ERROR_MODAL_SHARED_ID` - Main modal
- `ERROR_MODAL_TITLE_SHARED_ID` - Title section
- `ERROR_MODAL_MESSAGE_SHARED_ID` - Message body

---

## Integration with Dash

`handle_error()` function integrates with Dash's `on_error`:

```python
# In app.py
app = Dash(..., on_error=handle_error)
```

Flow:
1. Log error at DEBUG level
2. Check if custom error - log at ERROR with context
3. Extract error info for user message
4. Display modal via `set_props()`
5. Unhandled errors: log traceback, notify admin (TODO)

---

## Callback Error Patterns

### Inline validation errors
Return error message in callback output:
```python
@callback(...)
def validate_input(value):
    try:
        result = validate(value)
    except ValueError as e:
        return (dash.no_update, str(e), True)  # error message, disable button
    return (result, "", False)
```

### Guard conditions
Use `PreventUpdate` to stop execution:
```python
@callback(...)
def process_action(n_clicks, job_id):
    if n_clicks is None:
        raise PreventUpdate

    if job.status != JOB_STATUS_PENDING:
        log.warning(f"Cannot process - job status is {job.status}")
        raise PreventUpdate
```

### Background task errors
Update status on failure:
```python
try:
    # process
    job.model.status = JOB_STATUS_COMPLETED
except Exception as e:
    log.error(f"Error: {e}", exc_info=True)
    job.model.status = JOB_STATUS_FAILED
    raise
finally:
    job.save()
```
