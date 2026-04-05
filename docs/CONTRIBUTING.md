# Contributing to lakebase-ops-platform

## Getting Started

1. Clone the repository
2. Create a virtual environment: `python -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Install frontend dependencies: `cd app/frontend && npm install`

## Project Structure

```
agents/           # Agent mixin modules (health, provisioning, performance)
app/              # Databricks App (FastAPI backend + React frontend)
config/           # Settings, thresholds, policies
framework/        # Agent framework (event bus, base classes)
jobs/             # Databricks notebook-style jobs
sql/              # Centralized SQL query constants
utils/            # Shared utilities (client, alerting, delta writer)
tests/            # Test suite
docs/             # Documentation
```

## Development Workflow

1. Create a feature branch: `git checkout -b feat/your-feature main`
2. Make changes following the patterns in existing code
3. Run tests: `pytest tests/ -v`
4. Run frontend tests: `cd app/frontend && npm test`
5. Open a pull request against `main`

## Code Patterns

### Agent Mixins

All agent functionality is organized as mixin classes in `agents/<domain>/`. Each mixin:

- Inherits no base class (mixed into the agent class)
- Accesses `self.client` (LakebaseClient), `self.writer` (DeltaWriter), `self.alerts` (AlertManager)
- Uses `self.emit_event()` for cross-agent communication
- Logs via module-level `logger`

Example:
```python
class MyFeatureMixin:
    def my_tool(self, project_id: str, branch_id: str) -> dict:
        data = self.client.execute_query(project_id, branch_id, MY_SQL_QUERY)
        self.writer.write_metrics("table_name", [processed_data])
        return result
```

### SQL Queries

All SQL lives in `sql/queries.py` as named constants. Never inline SQL in agent code.

### Backend Routes

Routes in `app/backend/routers/` use `execute_query()` and `fqn()` from `sql_service.py`.
Use parameterized queries (`:param_name` syntax) for any user-controlled values.

### Adding a New Delta Table

1. Add the table name to `DELTA_TABLES` in `config/settings.py`
2. Add CREATE TABLE logic in `utils/delta_writer.py`
3. Reference via `fqn('table_name')` in backend routes

## Testing

- Backend: `pytest app/backend/tests/ -v`
- Frontend: `cd app/frontend && npm test`
- Agent tests: `pytest tests/ -v`

## Commit Messages

Use conventional format: `type(scope): description`

- `feat(agents)`: New agent tool or mixin
- `fix(backend)`: Bug fix in API layer
- `docs`: Documentation changes
- `refactor`: Code restructuring without behavior change
