import requests
from bs4 import BeautifulSoup
import re
import time
import csv

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def create_acronym(statute_name):
    year_match = re.search(r'\d{4}$', statute_name.strip())
    year = year_match.group(0) if year_match else ""
    name_base = statute_name[:-len(year)].strip() if year else statute_name
    
    skip_words = {'of', 'and', 'the', 'in', 'for', 'on', 'to', 'with', 'by'}
    return ''.join([word[0].upper() for word in name_base.split() 
                   if word.lower() not in skip_words and word]) + year

def get_statutes(base_url, max_pages=10):
    statutes = []
    seen = set()
    
    for page in range(max_pages):
        url = f"{base_url}/{page}" if page > 0 else base_url
        print(f"Fetching page {page+1}: {url}")
        
        try:
            response = requests.get(url, headers=HEADERS)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if not (table := soup.find('table', class_='browse-list')):
                print("No statutes table found")
                break
                
            links = [a.text.strip() for a in table.find_all('a', class_='non-ajax') 
                    if re.search(r'\d{4}$', a.text.strip())]
            
            new_statutes = [s for s in links if s not in seen]
            if not new_statutes:
                print("No new statutes found")
                break
                
            statutes.extend(new_statutes)
            seen.update(new_statutes)
            print(f"Added {len(new_statutes)} statutes")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"Error: {str(e)}")
            break
            
    return statutes

def get_provisions(statute_name):
    # retrieve provisions and their URLs
    acronym = create_acronym(statute_name)
    base_url = f"https://sso.agc.gov.sg/Act/{acronym}?WholeDoc=1"
    provisions = []
    
    try:
        response = requests.get(base_url, headers=HEADERS)
        if response.status_code != 200:
            return provisions
            
        soup = BeautifulSoup(response.content, 'html.parser')
        toc = soup.find('div', id='tocPanel')
        
        for link in (toc.find_all('a', class_='nav-link') if toc else []):
            if not (span := link.find('span')):
                continue
                
            text = span.get_text(strip=True)
            if match := re.match(r'^(\d+[A-Z]*)\s+(.+)', text):
                prov_num, title = match.groups()
                prov_id = link.get('href', '#').split('#')[-1]
                prov_url = f"https://sso.agc.gov.sg/Act/AA2004?WholeDoc=1&ProvIds={prov_id}#{prov_id}"
                
                content = soup.find(id=prov_id)
                content_text = content.get_text(strip=True) if content else ""
                
                provisions.append({
                    'number': prov_num,
                    'title': title,
                    'url': prov_url,
                    'content': content_text
                })
        
        return provisions
        
    except Exception as e:
        print(f"Error processing {statute_name}: {str(e)}")
        return []

def main():
    base_url = "https://sso.agc.gov.sg/Browse/Act/Current/All?PageSize=500&SortBy=Title&SortOrder=ASC"
    
    # get statutes
    print("Retrieving statutes...")
    statutes = get_statutes(base_url)
    
    # list of statutes
    with open('statutes.csv', 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows([["Statute Name"]] + [[s] for s in statutes])
    
    # provision finder test
    with open('provisions.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Statute", "Number", "Title", "URL", "Content"])
        
        for statute in statutes[:10]:  # limit to first 10 for testing
            print(f"\nProcessing: {statute}")
            for prov in get_provisions(statute):
                writer.writerow([
                    statute,
                    prov['number'],
                    prov['title'],
                    prov['url'],
                ])

if __name__ == "__main__":
    main()
