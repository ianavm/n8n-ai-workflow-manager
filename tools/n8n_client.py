"""
n8n REST API client.

Core client for interacting with n8n instances via REST API.
Handles workflow CRUD, execution management, credentials, and health checks.
Supports caching and retry logic.
"""

import json
import hashlib
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx


class N8nClient:
    """Core client for n8n REST API operations."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30,
                 max_retries: int = 3, cache_dir: Optional[str] = None):
        """
        Initialize n8n API client.

        Args:
            base_url: n8n instance URL (e.g., https://n8n.example.com)
            api_key: n8n API key
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure
            cache_dir: Directory for caching API responses
        """
        if not base_url:
            raise ValueError("n8n base URL is required")
        if not api_key:
            raise ValueError("n8n API key is required")

        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.max_retries = max_retries

        self.client = httpx.Client(
            base_url=f"{self.base_url}/api/v1",
            headers={
                'X-N8N-API-KEY': api_key,
                'Content-Type': 'application/json'
            },
            timeout=timeout
        )

        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent.parent / ".tmp" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # --- Health Check ---

    def health_check(self) -> Dict[str, Any]:
        """
        Test connectivity to n8n instance.

        Returns:
            Health status dictionary
        """
        try:
            response = self._request('GET', '/workflows', params={'limit': 1})
            return {
                'status': 'healthy',
                'base_url': self.base_url,
                'connected': True,
                'checked_at': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'base_url': self.base_url,
                'connected': False,
                'error': str(e),
                'checked_at': datetime.now().isoformat()
            }

    # --- Workflow CRUD ---

    def list_workflows(self, active_only: bool = False, tags: Optional[List[str]] = None,
                       use_cache: bool = True, cache_hours: int = 1) -> List[Dict[str, Any]]:
        """
        List all workflows.

        Args:
            active_only: Only return active workflows
            tags: Filter by tags
            use_cache: Whether to use cached results
            cache_hours: Cache validity in hours

        Returns:
            List of workflow dictionaries
        """
        cache_key = f"workflows_{'active' if active_only else 'all'}"

        if use_cache:
            cached = self._load_from_cache(cache_key, cache_hours)
            if cached:
                print(f"  Loaded {len(cached)} workflows from cache")
                return cached

        print(f"\nFetching workflows from {self.base_url}...")

        workflows = []
        cursor = None

        while True:
            params = {'limit': 100}
            if cursor:
                params['cursor'] = cursor
            if active_only:
                params['active'] = 'true'
            if tags:
                params['tags'] = ','.join(tags)

            data = self._request('GET', '/workflows', params=params)

            batch = data.get('data', data) if isinstance(data, dict) else data
            if isinstance(batch, list):
                workflows.extend(batch)
            elif isinstance(batch, dict) and 'data' in batch:
                workflows.extend(batch['data'])
            else:
                workflows.extend([batch] if batch else [])

            # Check pagination
            next_cursor = data.get('nextCursor') if isinstance(data, dict) else None
            if not next_cursor:
                break
            cursor = next_cursor

        print(f"  Found {len(workflows)} workflows")

        if use_cache:
            self._save_to_cache(cache_key, workflows)

        return workflows

    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get workflow by ID with full node details.

        Args:
            workflow_id: Workflow ID

        Returns:
            Complete workflow dictionary
        """
        return self._request('GET', f'/workflows/{workflow_id}')

    def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new workflow.

        Args:
            workflow_data: Workflow JSON definition

        Returns:
            Created workflow dictionary
        """
        result = self._request('POST', '/workflows', json_data=workflow_data)
        print(f"  Created workflow: {result.get('name', 'Unknown')} (ID: {result.get('id')})")
        return result

    def update_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing workflow.

        Args:
            workflow_id: Workflow ID
            workflow_data: Updated workflow JSON

        Returns:
            Updated workflow dictionary
        """
        result = self._request('PUT', f'/workflows/{workflow_id}', json_data=workflow_data)
        print(f"  Updated workflow: {result.get('name', 'Unknown')} (ID: {workflow_id})")
        return result

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if deleted successfully
        """
        self._request('DELETE', f'/workflows/{workflow_id}')
        print(f"  Deleted workflow: {workflow_id}")
        return True

    def activate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Activate a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Updated workflow dictionary
        """
        result = self._request('POST', f'/workflows/{workflow_id}/activate')
        print(f"  Activated workflow: {workflow_id}")
        return result

    def deactivate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Deactivate a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Updated workflow dictionary
        """
        result = self._request('POST', f'/workflows/{workflow_id}/deactivate')
        print(f"  Deactivated workflow: {workflow_id}")
        return result

    # --- Execution Management ---

    def list_executions(self, workflow_id: Optional[str] = None,
                        status: Optional[str] = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        List execution history.

        Args:
            workflow_id: Filter by workflow ID
            status: Filter by status (success, error, waiting)
            limit: Maximum results to return

        Returns:
            List of execution dictionaries
        """
        params = {'limit': min(limit, 250)}
        if workflow_id:
            params['workflowId'] = workflow_id
        if status:
            params['status'] = status

        data = self._request('GET', '/executions', params=params)

        executions = data.get('data', data) if isinstance(data, dict) else data
        if not isinstance(executions, list):
            executions = []

        return executions

    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Get execution details.

        Args:
            execution_id: Execution ID

        Returns:
            Execution detail dictionary
        """
        return self._request('GET', f'/executions/{execution_id}')

    def delete_execution(self, execution_id: str) -> bool:
        """
        Delete an execution record.

        Args:
            execution_id: Execution ID

        Returns:
            True if deleted
        """
        self._request('DELETE', f'/executions/{execution_id}')
        return True

    # --- Credential Management ---

    def list_credentials(self) -> List[Dict[str, Any]]:
        """
        List all credentials (metadata only, no secrets).

        Returns:
            List of credential metadata dictionaries
        """
        data = self._request('GET', '/credentials')
        credentials = data.get('data', data) if isinstance(data, dict) else data
        return credentials if isinstance(credentials, list) else []

    # --- Internal Methods ---

    def _request(self, method: str, endpoint: str,
                 params: Optional[Dict] = None,
                 json_data: Optional[Dict] = None) -> Any:
        """
        Make an API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            params: Query parameters
            json_data: Request body

        Returns:
            Response data

        Raises:
            Exception: On request failure after retries
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.request(
                    method=method,
                    url=endpoint,
                    params=params,
                    json=json_data
                )

                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    print(f"  Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()

                if response.status_code == 204:
                    return {}

                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (500, 502, 503):
                    wait_time = 2 ** attempt
                    print(f"  Server error ({e.response.status_code}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise

            except httpx.RequestError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"  Connection error. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise

        raise last_error or Exception("Request failed after retries")

    # --- Caching ---

    def _get_cache_key(self, key: str) -> str:
        """Generate cache filename from key."""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return f"n8n_{key_hash}"

    def _load_from_cache(self, key: str, cache_hours: int) -> Optional[List[Dict[str, Any]]]:
        """
        Load results from cache if available and not expired.

        Args:
            key: Cache key
            cache_hours: Maximum age of cache in hours

        Returns:
            Cached results or None
        """
        cache_key = self._get_cache_key(key)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if file_age > timedelta(hours=cache_hours):
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('results', [])
        except Exception:
            return None

    def _save_to_cache(self, key: str, data: Any):
        """
        Save results to cache.

        Args:
            key: Cache key
            data: Data to cache
        """
        cache_key = self._get_cache_key(key)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            cache_data = {
                'key': key,
                'cached_at': datetime.now().isoformat(),
                'count': len(data) if isinstance(data, list) else 1,
                'results': data
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  Warning: Failed to save cache: {e}")

    def save_results(self, data: Any, output_path: str):
        """
        Save results to JSON file.

        Args:
            data: Data to save
            output_path: Path to save JSON file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        output_data = {
            'timestamp': datetime.now().isoformat(),
            'source': self.base_url,
            'data': data
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n  Results saved to: {output_file}")


def main():
    """Main function for command-line usage."""
    import sys
    from config_loader import load_config

    try:
        config = load_config()

        api_key = config['api_keys']['n8n']
        if not api_key:
            print("Error: N8N_API_KEY not found in environment variables.")
            print("Please add it to your .env file.")
            sys.exit(1)

        base_url = config['n8n']['base_url']
        timeout = config['n8n'].get('timeout_seconds', 30)
        max_retries = config['n8n'].get('max_retries', 3)

        with N8nClient(base_url, api_key, timeout=timeout,
                       max_retries=max_retries,
                       cache_dir=config['paths']['cache_dir']) as client:

            # Health check
            print("=" * 50)
            print("N8N CONNECTION TEST")
            print("=" * 50)

            health = client.health_check()
            if health['connected']:
                print(f"  Status: CONNECTED")
                print(f"  Instance: {health['base_url']}")
            else:
                print(f"  Status: FAILED")
                print(f"  Error: {health.get('error', 'Unknown')}")
                sys.exit(1)

            # List workflows
            workflows = client.list_workflows(use_cache=False)

            print(f"\n{'=' * 50}")
            print("WORKFLOW SUMMARY")
            print(f"{'=' * 50}")
            print(f"Total Workflows: {len(workflows)}")

            active = [w for w in workflows if w.get('active')]
            inactive = [w for w in workflows if not w.get('active')]
            print(f"Active: {len(active)}")
            print(f"Inactive: {len(inactive)}")

            if workflows:
                print(f"\nRecent workflows:")
                for wf in workflows[:10]:
                    status = "ACTIVE" if wf.get('active') else "INACTIVE"
                    name = wf.get('name', 'Unnamed')[:50]
                    print(f"  [{status:8}] {name}")

            # Save results
            output_path = Path(config['paths']['tmp_dir']) / "workflows_list.json"
            client.save_results(workflows, str(output_path))

            print(f"\n  Connection test complete!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
