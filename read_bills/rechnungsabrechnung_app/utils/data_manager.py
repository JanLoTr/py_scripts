"""
Persistente Datenspeicherung und History-Management
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

class DataManager:
    """Verwaltet persistente Daten (JSON-basiert)"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.history_file = data_dir / "history.json"
        self.patterns_file = data_dir / "patterns.json"
        self.create_files_if_not_exist()
    
    def create_files_if_not_exist(self):
        """Erstellt JSON-Dateien falls nicht vorhanden"""
        self.data_dir.mkdir(exist_ok=True)
        
        if not self.history_file.exists():
            self.history_file.write_text(json.dumps({"invoices": []}, indent=2))
        
        if not self.patterns_file.exists():
            self.patterns_file.write_text(json.dumps({
                "product_patterns": {},
                "shop_preferences": {}
            }, indent=2))
    
    def save_invoice(self, invoice_data: Dict):
        """Speichert eine verarbeitete Rechnung in History"""
        try:
            history = self.load_history()
            
            invoice_entry = {
                "timestamp": datetime.now().isoformat(),
                "name": invoice_data.get("filename", "Unknown"),
                "shop": invoice_data.get("shop", "Unknown"),
                "total": invoice_data.get("total_amount", 0),
                "products": invoice_data.get("products", []),
                "splits": invoice_data.get("splits", {})
            }
            
            history["invoices"].append(invoice_entry)
            self.history_file.write_text(json.dumps(history, indent=2))
            return True
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")
            return False
    
    def load_history(self) -> Dict:
        """Lädt alle Rechnungen aus History"""
        try:
            if self.history_file.exists():
                return json.loads(self.history_file.read_text())
        except Exception as e:
            print(f"Fehler beim Laden der History: {e}")
        
        return {"invoices": []}
    
    def save_patterns(self, patterns: Dict):
        """Speichert erkannte Muster"""
        try:
            self.patterns_file.write_text(json.dumps(patterns, indent=2))
            return True
        except Exception as e:
            print(f"Fehler beim Speichern von Patterns: {e}")
            return False
    
    def load_patterns(self) -> Dict:
        """Lädt erkannte Muster"""
        try:
            if self.patterns_file.exists():
                return json.loads(self.patterns_file.read_text())
        except Exception as e:
            print(f"Fehler beim Laden von Patterns: {e}")
        
        return {"product_patterns": {}, "shop_preferences": {}}
    
    def get_statistics(self) -> Dict:
        """Generiert Statistiken aus History"""
        history = self.load_history()
        invoices = history.get("invoices", [])
        
        if not invoices:
            return {
                "total_invoices": 0,
                "total_spent": 0,
                "average_per_invoice": 0,
                "shops": {},
                "person1_total": 0,
                "person2_total": 0
            }
        
        total_spent = sum(inv.get("total", 0) for inv in invoices)
        
        # Shop-Statistiken
        shops = {}
        for inv in invoices:
            shop = inv.get("shop", "Unknown")
            if shop not in shops:
                shops[shop] = {"count": 0, "total": 0}
            shops[shop]["count"] += 1
            shops[shop]["total"] += inv.get("total", 0)
        
        # Person-Statistiken (aus Splits)
        person1_total = 0
        person2_total = 0
        
        for inv in invoices:
            products = inv.get("products", [])
            splits = inv.get("splits", {})
            
            for idx, product in enumerate(products):
                price = product.get("preis", 0) if isinstance(product, dict) else 0
                
                # Versuche Split zu finden
                for split_key, split_value in splits.items():
                    if str(idx) in str(split_key):
                        if isinstance(split_value, (list, tuple)) and len(split_value) >= 2:
                            p1_percent, p2_percent = split_value[0], split_value[1]
                            person1_total += price * (p1_percent / 100)
                            person2_total += price * (p2_percent / 100)
                            break
        
        return {
            "total_invoices": len(invoices),
            "total_spent": round(total_spent, 2),
            "average_per_invoice": round(total_spent / len(invoices) if invoices else 0, 2),
            "shops": shops,
            "person1_total": round(person1_total, 2),
            "person2_total": round(person2_total, 2)
        }
    
    def get_product_patterns(self, person1_name: str, person2_name: str) -> Dict:
        """
        Analysiert Produktmuster aus History
        
        Findet heraus:
        - Welche Produkte kauft Person 1 immer allein?
        - Welche sind immer 50/50?
        - Welche Muster gibt es?
        """
        history = self.load_history()
        invoices = history.get("invoices", [])
        
        product_patterns = {}
        
        for inv in invoices:
            products = inv.get("products", [])
            splits = inv.get("splits", {})
            
            for idx, product in enumerate(products):
                product_name = None
                price = 0
                
                # Handle both dict and potential other formats
                if isinstance(product, dict):
                    product_name = product.get("produkt", "Unknown")
                    price = float(product.get("preis", 0))
                else:
                    continue
                
                if product_name not in product_patterns:
                    product_patterns[product_name] = {
                        "count": 0,
                        "person1_100": 0,
                        "person2_100": 0,
                        "split_50_50": 0,
                        "splits": [],
                        "price_range": {"min": float('inf'), "max": 0},
                        "products": []  # Store products for price calculation
                    }
                
                pattern = product_patterns[product_name]
                pattern["count"] += 1
                pattern["products"].append(product)
                
                # Aktualisiere Preis-Range
                pattern["price_range"]["min"] = min(pattern["price_range"]["min"], price)
                pattern["price_range"]["max"] = max(pattern["price_range"]["max"], price)
                
                # Finde Split für dieses Produkt
                for split_key, split_value in splits.items():
                    if str(idx) in str(split_key):
                        if isinstance(split_value, (list, tuple)) and len(split_value) >= 2:
                            p1_percent, p2_percent = split_value[0], split_value[1]
                            pattern["splits"].append((p1_percent, p2_percent))
                            
                            if p1_percent == 100:
                                pattern["person1_100"] += 1
                            elif p2_percent == 100:
                                pattern["person2_100"] += 1
                            elif p1_percent == 50:
                                pattern["split_50_50"] += 1
                        break
        
        # Cleanup price_range
        for product_name in product_patterns:
            if product_patterns[product_name]["price_range"]["min"] == float('inf'):
                product_patterns[product_name]["price_range"] = None
            else:
                product_patterns[product_name]["price_range"] = {
                    "min": round(product_patterns[product_name]["price_range"]["min"], 2),
                    "max": round(product_patterns[product_name]["price_range"]["max"], 2)
                }
        
        return product_patterns
    
    def get_solo_buyer_products(self, person1_name: str, person2_name: str) -> Dict:
        """
        Findet Produkte die eine Person meistens allein kauft
        
        Returns:
        {
            "person1_solo": [...],  # Produkte wo Person1 >80% allein zahlt
            "person2_solo": [...],  # Produkte wo Person2 >80% allein zahlt
            "insights": [...]       # Interessante Erkenntnisse
        }
        """
        patterns = self.get_product_patterns(person1_name, person2_name)
        
        person1_solo = []
        person2_solo = []
        insights = []
        
        for product_name, pattern in patterns.items():
            if pattern["count"] < 2:  # Mindestens 2x gekauft
                continue
            
            total_purchases = pattern["count"]
            p1_solo_ratio = pattern["person1_100"] / total_purchases
            p2_solo_ratio = pattern["person2_100"] / total_purchases
            
            # Solo-Kriterium: >80% alleine gekauft
            if p1_solo_ratio >= 0.8:
                person1_solo.append({
                    "produkt": product_name,
                    "solo_ratio": round(p1_solo_ratio * 100, 1),
                    "mal_gekauft": total_purchases,
                    "price_avg": round(
                        sum(p["preis"] for p in pattern.get("products", [])) / total_purchases 
                        if pattern.get("products") else 0, 2
                    ) if "products" in pattern else None
                })
            
            if p2_solo_ratio >= 0.8:
                person2_solo.append({
                    "produkt": product_name,
                    "solo_ratio": round(p2_solo_ratio * 100, 1),
                    "mal_gekauft": total_purchases,
                    "price_avg": None
                })
            
            # Interessante Insights
            if p1_solo_ratio >= 0.8:
                insights.append(f"🔴 {person1_name} kauft '{product_name}' {pattern['person1_100']}x für sich allein")
            elif p2_solo_ratio >= 0.8:
                insights.append(f"🔵 {person2_name} kauft '{product_name}' {pattern['person2_100']}x für sich allein")
            elif pattern["split_50_50"] == total_purchases:
                insights.append(f"🤝 '{product_name}' wird IMMER 50/50 aufgeteilt")
        
        return {
            "person1_solo": person1_solo,
            "person2_solo": person2_solo,
            "insights": insights,
            "total_patterns": len(patterns)
        }
