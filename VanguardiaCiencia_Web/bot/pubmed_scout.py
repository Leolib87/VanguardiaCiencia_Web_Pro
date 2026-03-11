import requests
import xml.etree.ElementTree as ET
import json
from pathlib import Path

def search_pubmed(query, max_results=5):
    """Busca en PubMed y retorna los detalles de los últimos artículos."""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    # 1. Buscar IDs de artículos
    search_url = f"{base_url}esearch.fcgi?db=pubmed&term={query}&retmax={max_results}&retmode=json&sort=pub_date"
    try:
        response = requests.get(search_url)
        ids = response.json().get('esearchresult', {}).get('idlist', [])
        if not ids: return []
        
        # 2. Obtener resúmenes de esos IDs
        id_str = ",".join(ids)
        summary_url = f"{base_url}esummary.fcgi?db=pubmed&id={id_str}&retmode=json"
        summary_res = requests.get(summary_url).json()
        
        results = []
        for uid in ids:
            item = summary_res.get('result', {}).get(uid, {})
            if item:
                title = item.get('title', 'Sin título')
                pub_date = item.get('pubdate', 'N/A')
                # Construir link directo
                link = f"https://pubmed.ncbi.nlm.nih.gov/{uid}/"
                results.append({
                    "title": title,
                    "link": link,
                    "source": "PubMed Central",
                    "date": pub_date
                })
        return results
    except Exception as e:
        print(f"Error en PubMed: {e}")
        return []

if __name__ == "__main__":
    # Prueba rápida
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "cancer"
    print(json.dumps(search_pubmed(q), indent=2))
