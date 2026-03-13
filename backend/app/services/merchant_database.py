"""Austrian merchant database for OCR recognition"""
from typing import Dict, Optional, List
from decimal import Decimal
from enum import Enum


class ExpenseCategory(str, Enum):
    """Expense categories for merchant classification"""

    GROCERIES = "groceries"
    OFFICE_SUPPLIES = "office_supplies"
    EQUIPMENT = "equipment"
    MAINTENANCE = "maintenance"
    UTILITIES = "utilities"
    PROFESSIONAL_SERVICES = "professional_services"
    MARKETING = "marketing"
    TRAVEL = "travel"
    INSURANCE = "insurance"
    OTHER = "other"


class MerchantInfo:
    """Information about a merchant"""

    def __init__(
        self,
        official_name: str,
        category: ExpenseCategory,
        vat_rate: Decimal,
        keywords: List[str],
        is_austrian: bool = True,
    ):
        self.official_name = official_name
        self.category = category
        self.vat_rate = vat_rate
        self.keywords = keywords
        self.is_austrian = is_austrian


class MerchantDatabase:
    """Database of common Austrian merchants for OCR recognition"""

    def __init__(self):
        self.merchants = self._load_merchants()
        self.custom_merchants: Dict[str, MerchantInfo] = {}

    def _load_merchants(self) -> Dict[str, MerchantInfo]:
        """Load known Austrian merchants"""
        return {
            # Supermarkets
            "billa": MerchantInfo(
                official_name="BILLA AG",
                category=ExpenseCategory.GROCERIES,
                vat_rate=Decimal("0.20"),
                keywords=["billa", "billa ag", "billa plus"],
                is_austrian=True,
            ),
            "spar": MerchantInfo(
                official_name="SPAR Österreich",
                category=ExpenseCategory.GROCERIES,
                vat_rate=Decimal("0.20"),
                keywords=["spar", "interspar", "eurospar"],
                is_austrian=True,
            ),
            "hofer": MerchantInfo(
                official_name="HOFER KG",
                category=ExpenseCategory.GROCERIES,
                vat_rate=Decimal("0.20"),
                keywords=["hofer", "hofer kg"],
                is_austrian=True,
            ),
            "lidl": MerchantInfo(
                official_name="Lidl Österreich",
                category=ExpenseCategory.GROCERIES,
                vat_rate=Decimal("0.20"),
                keywords=["lidl", "lidl österreich"],
                is_austrian=True,
            ),
            "merkur": MerchantInfo(
                official_name="MERKUR",
                category=ExpenseCategory.GROCERIES,
                vat_rate=Decimal("0.20"),
                keywords=["merkur", "merkur markt"],
                is_austrian=True,
            ),
            "penny": MerchantInfo(
                official_name="PENNY",
                category=ExpenseCategory.GROCERIES,
                vat_rate=Decimal("0.20"),
                keywords=["penny", "penny markt"],
                is_austrian=True,
            ),
            # Hardware stores
            "obi": MerchantInfo(
                official_name="OBI Bau- und Heimwerkermärkte",
                category=ExpenseCategory.MAINTENANCE,
                vat_rate=Decimal("0.20"),
                keywords=["obi", "obi markt"],
                is_austrian=False,
            ),
            "baumax": MerchantInfo(
                official_name="bauMax",
                category=ExpenseCategory.MAINTENANCE,
                vat_rate=Decimal("0.20"),
                keywords=["baumax", "bau max"],
                is_austrian=True,
            ),
            "hornbach": MerchantInfo(
                official_name="HORNBACH",
                category=ExpenseCategory.MAINTENANCE,
                vat_rate=Decimal("0.20"),
                keywords=["hornbach"],
                is_austrian=False,
            ),
            "bauhaus": MerchantInfo(
                official_name="BAUHAUS",
                category=ExpenseCategory.MAINTENANCE,
                vat_rate=Decimal("0.20"),
                keywords=["bauhaus"],
                is_austrian=False,
            ),
            # Drugstores
            "dm": MerchantInfo(
                official_name="dm drogerie markt",
                category=ExpenseCategory.GROCERIES,
                vat_rate=Decimal("0.20"),
                keywords=["dm", "dm drogerie"],
                is_austrian=False,
            ),
            "müller": MerchantInfo(
                official_name="Müller Drogerie",
                category=ExpenseCategory.GROCERIES,
                vat_rate=Decimal("0.20"),
                keywords=["müller", "mueller"],
                is_austrian=False,
            ),
            "bipa": MerchantInfo(
                official_name="BIPA",
                category=ExpenseCategory.GROCERIES,
                vat_rate=Decimal("0.20"),
                keywords=["bipa"],
                is_austrian=True,
            ),
            # Electronics
            "mediamarkt": MerchantInfo(
                official_name="MediaMarkt",
                category=ExpenseCategory.EQUIPMENT,
                vat_rate=Decimal("0.20"),
                keywords=["mediamarkt", "media markt"],
                is_austrian=False,
            ),
            "saturn": MerchantInfo(
                official_name="Saturn",
                category=ExpenseCategory.EQUIPMENT,
                vat_rate=Decimal("0.20"),
                keywords=["saturn"],
                is_austrian=False,
            ),
            # Office supplies
            "libro": MerchantInfo(
                official_name="LIBRO",
                category=ExpenseCategory.OFFICE_SUPPLIES,
                vat_rate=Decimal("0.20"),
                keywords=["libro"],
                is_austrian=True,
            ),
            "pagro": MerchantInfo(
                official_name="PAGRO DISKONT",
                category=ExpenseCategory.OFFICE_SUPPLIES,
                vat_rate=Decimal("0.20"),
                keywords=["pagro", "pagro diskont"],
                is_austrian=True,
            ),
            # Furniture
            "ikea": MerchantInfo(
                official_name="IKEA",
                category=ExpenseCategory.EQUIPMENT,
                vat_rate=Decimal("0.20"),
                keywords=["ikea"],
                is_austrian=False,
            ),
            "xxxlutz": MerchantInfo(
                official_name="XXXLutz",
                category=ExpenseCategory.EQUIPMENT,
                vat_rate=Decimal("0.20"),
                keywords=["xxxlutz", "lutz"],
                is_austrian=True,
            ),
            # Gas stations
            "omv": MerchantInfo(
                official_name="OMV",
                category=ExpenseCategory.TRAVEL,
                vat_rate=Decimal("0.20"),
                keywords=["omv"],
                is_austrian=True,
            ),
            "bp": MerchantInfo(
                official_name="BP",
                category=ExpenseCategory.TRAVEL,
                vat_rate=Decimal("0.20"),
                keywords=["bp"],
                is_austrian=False,
            ),
            "shell": MerchantInfo(
                official_name="Shell",
                category=ExpenseCategory.TRAVEL,
                vat_rate=Decimal("0.20"),
                keywords=["shell"],
                is_austrian=False,
            ),
            # Pharmacies
            "apotheke": MerchantInfo(
                official_name="Apotheke",
                category=ExpenseCategory.OTHER,
                vat_rate=Decimal("0.20"),
                keywords=["apotheke"],
                is_austrian=True,
            ),
        }

    def lookup_merchant(self, name: str) -> Optional[MerchantInfo]:
        """
        Look up merchant by name

        Args:
            name: Merchant name (case-insensitive)

        Returns:
            MerchantInfo if found, None otherwise
        """
        name_lower = name.lower()

        # Check known merchants
        for key, merchant_info in self.merchants.items():
            if key in name_lower:
                return merchant_info

        # Check custom merchants
        for key, merchant_info in self.custom_merchants.items():
            if key in name_lower:
                return merchant_info

        return None

    def get_merchant_category(self, name: str) -> Optional[ExpenseCategory]:
        """
        Get expense category for merchant

        Args:
            name: Merchant name

        Returns:
            ExpenseCategory if found, None otherwise
        """
        merchant_info = self.lookup_merchant(name)
        return merchant_info.category if merchant_info else None

    def get_merchant_vat_rate(self, name: str) -> Optional[Decimal]:
        """
        Get VAT rate for merchant

        Args:
            name: Merchant name

        Returns:
            VAT rate if found, None otherwise
        """
        merchant_info = self.lookup_merchant(name)
        return merchant_info.vat_rate if merchant_info else None

    def add_custom_merchant(
        self,
        name: str,
        official_name: str,
        category: ExpenseCategory,
        vat_rate: Decimal = Decimal("0.20"),
    ) -> None:
        """
        Add custom merchant for user-specific learning

        Args:
            name: Merchant identifier (lowercase)
            official_name: Official merchant name
            category: Expense category
            vat_rate: VAT rate (default 20%)
        """
        key = name.lower()
        self.custom_merchants[key] = MerchantInfo(
            official_name=official_name,
            category=category,
            vat_rate=vat_rate,
            keywords=[key],
            is_austrian=True,
        )

    def get_all_merchants(self) -> List[str]:
        """
        Get list of all known merchant names

        Returns:
            List of merchant official names
        """
        merchants = [info.official_name for info in self.merchants.values()]
        merchants.extend([info.official_name for info in self.custom_merchants.values()])
        return sorted(merchants)

    def get_merchants_by_category(self, category: ExpenseCategory) -> List[str]:
        """
        Get merchants by category

        Args:
            category: Expense category

        Returns:
            List of merchant names in category
        """
        merchants = []

        for merchant_info in self.merchants.values():
            if merchant_info.category == category:
                merchants.append(merchant_info.official_name)

        for merchant_info in self.custom_merchants.values():
            if merchant_info.category == category:
                merchants.append(merchant_info.official_name)

        return sorted(merchants)

    def is_austrian_merchant(self, name: str) -> bool:
        """
        Check if merchant is Austrian

        Args:
            name: Merchant name

        Returns:
            True if Austrian, False otherwise
        """
        merchant_info = self.lookup_merchant(name)
        return merchant_info.is_austrian if merchant_info else False

    def search_merchants(self, query: str) -> List[MerchantInfo]:
        """
        Search merchants by query

        Args:
            query: Search query

        Returns:
            List of matching merchants
        """
        query_lower = query.lower()
        results = []

        for merchant_info in self.merchants.values():
            if any(query_lower in keyword for keyword in merchant_info.keywords):
                results.append(merchant_info)

        for merchant_info in self.custom_merchants.values():
            if any(query_lower in keyword for keyword in merchant_info.keywords):
                results.append(merchant_info)

        return results

