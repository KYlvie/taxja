"""
PSD2 API Client for Direct Bank Integration

PSD2 (Payment Services Directive 2) enables third-party access to bank accounts
with user consent. This client implements OAuth2 flow and transaction fetching.

Note: This is a generic implementation. Each bank may have specific requirements.
Austrian banks supporting PSD2:
- Raiffeisen
- Erste Bank
- Sparkasse
- Bank Austria
- BAWAG P.S.K.

Requirements:
- Bank-specific API credentials (client_id, client_secret)
- User consent via OAuth2 flow
- Valid access tokens
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal
from enum import Enum


class PSD2Provider(str, Enum):
    """Supported PSD2 providers"""
    RAIFFEISEN = "raiffeisen"
    ERSTE_BANK = "erste_bank"
    SPARKASSE = "sparkasse"
    BANK_AUSTRIA = "bank_austria"
    BAWAG = "bawag"
    GENERIC = "generic"


class PSD2Client:
    """
    Generic PSD2 API client
    
    Implements OAuth2 authorization flow and transaction fetching
    according to Berlin Group NextGenPSD2 standard.
    """
    
    # Provider-specific endpoints (examples - actual URLs vary)
    PROVIDER_ENDPOINTS = {
        PSD2Provider.RAIFFEISEN: {
            "base_url": "https://api.raiffeisen.at/psd2",
            "auth_url": "https://auth.raiffeisen.at/oauth2/authorize",
            "token_url": "https://auth.raiffeisen.at/oauth2/token",
        },
        PSD2Provider.ERSTE_BANK: {
            "base_url": "https://api.erstebank.at/psd2",
            "auth_url": "https://auth.erstebank.at/oauth2/authorize",
            "token_url": "https://auth.erstebank.at/oauth2/token",
        },
        # Add other providers as needed
    }
    
    def __init__(
        self,
        provider: PSD2Provider,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ):
        """
        Initialize PSD2 client
        
        Args:
            provider: Bank provider
            client_id: OAuth2 client ID (from bank developer portal)
            client_secret: OAuth2 client secret
            redirect_uri: OAuth2 redirect URI (must match registration)
        """
        self.provider = provider
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        
        # Get provider endpoints
        self.endpoints = self.PROVIDER_ENDPOINTS.get(
            provider,
            {
                "base_url": "",
                "auth_url": "",
                "token_url": "",
            }
        )
        
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
    
    def get_authorization_url(self, state: str, scope: str = "aisp") -> str:
        """
        Get OAuth2 authorization URL for user consent
        
        Args:
            state: Random state parameter for CSRF protection
            scope: OAuth2 scope (aisp = Account Information Service Provider)
        
        Returns:
            Authorization URL to redirect user to
        """
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
        
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.endpoints['auth_url']}?{query_string}"
    
    def exchange_code_for_token(self, authorization_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token
        
        Args:
            authorization_code: Code received from OAuth2 callback
        
        Returns:
            Token response with access_token, refresh_token, expires_in
        """
        
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        response = requests.post(
            self.endpoints["token_url"],
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        
        response.raise_for_status()
        token_data = response.json()
        
        # Store tokens
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token")
        
        expires_in = token_data.get("expires_in", 3600)
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        return token_data
    
    def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refresh access token using refresh token
        
        Returns:
            New token response
        """
        
        if not self.refresh_token:
            raise ValueError("No refresh token available")
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        response = requests.post(
            self.endpoints["token_url"],
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        
        response.raise_for_status()
        token_data = response.json()
        
        # Update tokens
        self.access_token = token_data["access_token"]
        if "refresh_token" in token_data:
            self.refresh_token = token_data["refresh_token"]
        
        expires_in = token_data.get("expires_in", 3600)
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        return token_data
    
    def _ensure_valid_token(self):
        """Ensure access token is valid, refresh if needed"""
        
        if not self.access_token:
            raise ValueError("No access token available. Please authorize first.")
        
        # Check if token is expired or about to expire (5 min buffer)
        if self.token_expires_at and datetime.now() >= self.token_expires_at - timedelta(minutes=5):
            self.refresh_access_token()
    
    def _make_api_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make authenticated API request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional request parameters
        
        Returns:
            API response as dictionary
        """
        
        self._ensure_valid_token()
        
        url = f"{self.endpoints['base_url']}{endpoint}"
        
        headers = kwargs.pop("headers", {})
        headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        })
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            **kwargs
        )
        
        response.raise_for_status()
        return response.json()
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        """
        Get list of user's bank accounts
        
        Returns:
            List of account dictionaries with id, iban, currency, etc.
        """
        
        response = self._make_api_request("GET", "/v1/accounts")
        
        # Berlin Group standard response format
        accounts = response.get("accounts", [])
        
        return [
            {
                "id": acc.get("resourceId"),
                "iban": acc.get("iban"),
                "currency": acc.get("currency"),
                "name": acc.get("name"),
                "product": acc.get("product"),
                "balance": acc.get("balances", [{}])[0].get("balanceAmount", {}).get("amount"),
            }
            for acc in accounts
        ]
    
    def get_transactions(
        self,
        account_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get transactions for a specific account
        
        Args:
            account_id: Account resource ID
            date_from: Start date for transactions (default: 90 days ago)
            date_to: End date for transactions (default: today)
        
        Returns:
            List of transaction dictionaries
        """
        
        # Default date range: last 90 days
        if not date_from:
            date_from = datetime.now() - timedelta(days=90)
        if not date_to:
            date_to = datetime.now()
        
        params = {
            "dateFrom": date_from.strftime("%Y-%m-%d"),
            "dateTo": date_to.strftime("%Y-%m-%d"),
        }
        
        response = self._make_api_request(
            "GET",
            f"/v1/accounts/{account_id}/transactions",
            params=params
        )
        
        # Parse transactions from Berlin Group format
        transactions_data = response.get("transactions", {})
        booked = transactions_data.get("booked", [])
        pending = transactions_data.get("pending", [])
        
        parsed_transactions = []
        
        for txn in booked + pending:
            parsed_transactions.append(self._parse_transaction(txn))
        
        return parsed_transactions
    
    def _parse_transaction(self, txn: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse transaction from Berlin Group format to internal format
        
        Args:
            txn: Transaction data from API
        
        Returns:
            Parsed transaction dictionary
        """
        
        # Extract amount
        amount_data = txn.get("transactionAmount", {})
        amount_str = amount_data.get("amount", "0")
        currency = amount_data.get("currency", "EUR")
        
        # Parse amount (may be negative for debits)
        amount = Decimal(amount_str)
        
        # Extract date
        date_str = txn.get("bookingDate") or txn.get("valueDate")
        date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
        
        # Extract description
        description_parts = []
        if txn.get("remittanceInformationUnstructured"):
            description_parts.append(txn["remittanceInformationUnstructured"])
        if txn.get("creditorName"):
            description_parts.append(txn["creditorName"])
        if txn.get("debtorName"):
            description_parts.append(txn["debtorName"])
        
        description = " - ".join(description_parts) if description_parts else "Unknown"
        
        return {
            "date": date,
            "amount": amount,
            "description": description,
            "reference": txn.get("transactionId") or txn.get("endToEndId"),
            "currency": currency,
            "creditor_name": txn.get("creditorName"),
            "debtor_name": txn.get("debtorName"),
            "creditor_iban": txn.get("creditorAccount", {}).get("iban"),
            "debtor_iban": txn.get("debtorAccount", {}).get("iban"),
            "raw_data": txn,
        }
    
    def get_balances(self, account_id: str) -> List[Dict[str, Any]]:
        """
        Get account balances
        
        Args:
            account_id: Account resource ID
        
        Returns:
            List of balance dictionaries
        """
        
        response = self._make_api_request(
            "GET",
            f"/v1/accounts/{account_id}/balances"
        )
        
        balances = response.get("balances", [])
        
        return [
            {
                "type": bal.get("balanceType"),
                "amount": Decimal(bal.get("balanceAmount", {}).get("amount", "0")),
                "currency": bal.get("balanceAmount", {}).get("currency"),
                "date": bal.get("referenceDate"),
            }
            for bal in balances
        ]


class PSD2Service:
    """
    High-level service for PSD2 integration
    
    Manages multiple bank connections and provides unified interface
    """
    
    def __init__(self):
        """Initialize PSD2 service"""
        self.clients: Dict[str, PSD2Client] = {}
    
    def register_client(
        self,
        user_id: int,
        provider: PSD2Provider,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> str:
        """
        Register a new PSD2 client for a user
        
        Returns:
            Client key for future reference
        """
        
        client_key = f"{user_id}_{provider.value}"
        
        self.clients[client_key] = PSD2Client(
            provider=provider,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
        
        return client_key
    
    def get_client(self, client_key: str) -> PSD2Client:
        """Get registered PSD2 client"""
        
        if client_key not in self.clients:
            raise ValueError(f"No client registered with key: {client_key}")
        
        return self.clients[client_key]
    
    def import_transactions_from_bank(
        self,
        client_key: str,
        account_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Import transactions directly from bank via PSD2
        
        Args:
            client_key: Registered client key
            account_id: Bank account ID
            date_from: Start date
            date_to: End date
        
        Returns:
            List of transactions
        """
        
        client = self.get_client(client_key)
        return client.get_transactions(account_id, date_from, date_to)
