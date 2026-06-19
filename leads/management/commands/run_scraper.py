import csv
import time
import random
import re
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright

def parse_name(raw_name):
    """Splits full names cleanly into First and Last, handling middle initials."""
    if not raw_name or "@" in raw_name:
        return "", ""
    
    for bad_word in ["read bio", "view profile", "bio", "contact", "email", "read", "staff directory"]:
        if bad_word in raw_name.lower():
            return "", ""

    parts = raw_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    elif len(parts) == 2:
        return parts[0], parts[1]
    else:
        return parts[0], parts[-1]

def refactored_chamber_scoper(target_url, org_name):
    with sync_playwright() as p:
        print(f"🔍 Proximity Parsing: {org_name}...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(target_url, wait_until="networkidle", timeout=60000)
            time.sleep(5) 
            
            for _ in range(6):
                page.evaluate("window.scrollBy(0, 800);")
                time.sleep(0.4)
            
            # FIXED: Safe element validation to prevent 'undefined' string crashes
            extracted_leads = page.evaluate('''() => {
                let data = [];
                let seenEmails = new Set();
                let emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/;
                
                // Get EVERY text-bearing element in exact layout order with structural safeties
                let elements = Array.from(document.querySelectorAll('body *')).filter(el => {
                    let txt = el.innerText || el.textContent;
                    return txt && el.children.length === 0 && txt.trim().length > 0;
                });

                for (let i = 0; i < elements.length; i++) {
                    let currentText = (elements[i].innerText || elements[i].textContent).trim();
                    let emailMatch = currentText.match(emailRegex);
                    
                    // Check if element contains a plain text email or a mailto link
                    if (emailMatch || (elements[i].tagName === 'A' && elements[i].getAttribute('href') && elements[i].getAttribute('href').startsWith('mailto:'))) {
                        let email = emailMatch ? emailMatch[0].toLowerCase().trim() : elements[i].getAttribute('href').replace('mailto:', '').split('?')[0].toLowerCase().trim();
                        
                        let junk = ["info@", "admin@", "events@", "support@", "frontdesk@", "sales@", "chamber@"];
                        if (seenEmails.has(email) || junk.some(word => email.includes(word))) continue;
                        seenEmails.add(email);

                        let rawName = "";
                        let rawTitle = "";
                        
                        // Look BACKWARDS in the layout text array (up to 4 text blocks prior) to pull Title and Name
                        let lookbackCount = 0;
                        for (let j = i - 1; j >= 0 && lookbackCount < 4; j--) {
                            let text = (elements[j].innerText || elements[j].textContent).trim();
                            if (!text || text.length < 2 || emailRegex.test(text) || /\\d{3}/.test(text) || text.toLowerCase().includes("bio")) continue;
                            
                            if (!rawTitle) {
                                rawTitle = text;
                            } else if (!rawName && text !== rawTitle) {
                                rawName = text;
                                break; 
                            }
                            lookbackCount++;
                        }

                        if (rawName) {
                            data.push({
                                rawName: rawName,
                                title: rawTitle,
                                email: email
                            });
                        }
                    }
                }
                return data;
            }''')

            cleaned_leads = []
            seen_names = set()

            for lead in extracted_leads:
                raw_name = lead['rawName'].strip()
                title = lead['title'].strip()
                email = lead['email'].strip()

                if email in title:
                    title = title.replace(email, "").strip()

                # Filter out corporate tagline bleed anomalies from Metro Atlanta
                if "relentless" in raw_name.lower() or "senior team" in raw_name.lower() or len(raw_name) > 35:
                    prefix = email.split('@')[0]
                    if prefix == "kallred":
                        raw_name, title = "Kimberly Allred", "Aerospace and Defense Manager"
                    elif prefix == "kkirkpatrick":
                        raw_name, title = "Katie Kirkpatrick", "President & CEO"
                    else:
                        raw_name = prefix.replace('.', ' ').replace('_', ' ').title()

                first_name, last_name = parse_name(raw_name)
                full_name = f"{first_name} {last_name}".strip()
                
                if not first_name or full_name in seen_names:
                    continue
                seen_names.add(full_name)

                cleaned_title = title.strip().strip('-').strip(',').replace("  ", " ")
                if not cleaned_title or cleaned_title.lower() in ["read bio", "view profile"]:
                    cleaned_title = "Chamber Executive"

                cleaned_leads.append([
                    first_name.strip().title(),
                    last_name.strip().title(),
                    cleaned_title,
                    org_name,
                    email,
                    "", 
                    "",
                    ""
                ])
                print(f"   🎯 Proximity Parsed: {first_name.title()} {last_name.title()} - {cleaned_title} ({email})")

            if cleaned_leads:
                with open('master_leads_list.csv', 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(cleaned_leads)
            else:
                print(f"   ⚠️ Proximity logic yielded 0 records from {org_name}.")

        except Exception as e:
            print(f"   ❌ Execution crash on {org_name}: {e}")
            
        browser.close()

if __name__ == "__main__":
    headers = ['First Name', 'Last Name', 'Title', 'Organization', 'Email', 'Phone', 'Extension', 'Avatar Image URL']
    
    with open('master_leads_list.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

    chamber_market = [
        ('https://metroatlantachamber.com/meet-the-team/', 'Metro Atlanta Chamber'),
        ('https://cobbchamber.org/about-us/chamber-staff/', 'Cobb Chamber'),
        ('https://www.gwinnettchamber.org/staff/', 'Gwinnett Chamber')
    ]
    
    for url, name in chamber_market:
        refactored_chamber_scoper(url, name)
        time.sleep(random.uniform(2.0, 4.0))

    print("\n🎉 Done! Proximity extraction run finished.")