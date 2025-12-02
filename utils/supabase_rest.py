"""Direct Supabase REST API client to bypass Python SDK issues."""

import os
import requests
from typing import Dict, List, Optional, Any
from utils.logger import log_info, log_error


class SupabaseRestClient:
    """Simple REST client for Supabase that bypasses SDK proxy issues."""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip('/')
        self.key = key
        self.headers = {
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }

    def table(self, table_name: str):
        """Return a table interface."""
        return SupabaseTable(self, table_name)

    def _request(self, method: str, endpoint: str, json: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        """Make HTTP request to Supabase."""
        url = f"{self.url}/rest/v1/{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json,
                params=params,
                timeout=30
            )
            if response.status_code >= 400:
                log_error(f"Supabase request failed: {method} {url}")
                log_error(f"Status: {response.status_code}")
                log_error(f"Response: {response.text}")
            response.raise_for_status()
            return response.json() if response.content else {}
        except Exception as e:
            log_error(f"Supabase REST error: {e}")
            raise


class SupabaseTable:
    """Table interface for REST operations."""

    def __init__(self, client: SupabaseRestClient, table_name: str):
        self.client = client
        self.table_name = table_name
        self._filters = []
        self._select_fields = '*'
        self._order_by = None
        self._limit_val = None

    def select(self, fields: str = '*'):
        """Select fields."""
        self._select_fields = fields
        return self

    def eq(self, column: str, value: Any):
        """Equal filter."""
        self._filters.append(f"{column}=eq.{value}")
        return self

    def gte(self, column: str, value: Any):
        """Greater than or equal filter."""
        self._filters.append(f"{column}=gte.{value}")
        return self

    def lte(self, column: str, value: Any):
        """Less than or equal filter."""
        self._filters.append(f"{column}=lte.{value}")
        return self

    def order(self, column: str, desc: bool = False):
        """Order results."""
        self._order_by = f"{column}.{'desc' if desc else 'asc'}"
        return self

    def limit(self, count: int):
        """Limit results."""
        self._limit_val = count
        return self

    def insert(self, data: Dict):
        """Insert data - returns self for chaining."""
        self._insert_data = data
        return self

    def update(self, data: Dict):
        """Update data - returns self for chaining."""
        self._update_data = data
        return self

    def delete(self):
        """Delete data - returns self for chaining."""
        self._is_delete = True
        return self

    def execute(self):
        """Execute query."""
        params = self._build_params()

        # Check if this is an update operation
        if hasattr(self, '_update_data'):
            result = self.client._request('PATCH', self.table_name, json=self._update_data, params=params)
            return ExecuteResult(result)

        # Check if this is a delete operation
        if hasattr(self, '_is_delete'):
            result = self.client._request('DELETE', self.table_name, params=params)
            return ExecuteResult(result)

        # Check if this is an insert operation
        if hasattr(self, '_insert_data'):
            result = self.client._request('POST', self.table_name, json=self._insert_data, params=params)
            return ExecuteResult(result)

        # Default to SELECT
        result = self.client._request('GET', self.table_name, params=params)
        return ExecuteResult(result)

    def single(self):
        """Get single result."""
        self._limit_val = 1
        result = self.execute()
        result.data = result.data[0] if result.data else None
        return result

    def _build_params(self) -> Dict:
        """Build query parameters."""
        params = {'select': self._select_fields}
        if self._filters:
            for f in self._filters:
                key, val = f.split('=', 1)
                params[key] = val
        if self._order_by:
            params['order'] = self._order_by
        if self._limit_val:
            params['limit'] = self._limit_val
        return params


class ExecuteResult:
    """Result wrapper."""

    def __init__(self, data):
        self.data = data if isinstance(data, list) else [data] if data else []
