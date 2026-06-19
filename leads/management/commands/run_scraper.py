import os
import time
import random
import re
import urllib.parse
import json

# Force Django to allow database operations inside Playwright's loop context
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand
from playwright.sync_api import sync_playwright
from nameparser import HumanName

# 🛡️ FIXED: Absolute path import explicitly maps to your app models directory
from leads.models import ChamberLead, ChamberDirectory, ChamberRequest, Order, OrderItem, UserPurchase

# 🛡️ THE HIGH-FIDELITY EXTRACTION FILTER MATRIX
BLACKLIST_KEYWORDS = (
    'camping', 'toll', 'road', 'download', 'pdf', 'excel', 'word', 'powerpoint',
    'trip', 'guide', 'visit', 'follow us', 'our mission', 'privacy policy', 
    'terms of service', 'about us', 'contact us', 'newsletter', 'copyright',
    'explore', 'vacation', 'listing', 'advertisement', 'heritage', 'gallery',
    'board of directors', 'executive committee', 'history', 'foundation'
)

# Hard exclusion patterns for structural mailboxes
GENERIC_BOXES = ('info@', 'support@', 'admin@', 'marketing@', 'contact@', 'webmaster@', 'help@', 'membership@', 'events@', 'join@', 'chamber@', 'frontdesk@', 'sales@')

# Strict keywords to instantly identify and drop corporate entities, initiatives, or B2B program titles
ORGANIZATION_KEYWORDS = (
    'business', 'center', 'visitor', 'council', 'service', 'chamber', 'association',
    'alliance', 'bureau', 'corporation', 'company', 'inc.', 'llc', 'group', 'dept',
    'department', 'practices', 'committee', 'board', 'foundation', 'development',
    'partnership', 'network', 'agency', 'institute', 'society', 'club'
)


def is_valid_human_name(name_str):
    """
    Rigorously validates if a string is structured like an actual human name.
    Uses the nameparser library coupled with strict structural guardrails.
    """
    if not name_str:
        return False
        
    clean_str = name_str.strip()
    
    # Threshold check: Names aren't tiny, massive, and don't contain emails
    if len(clean_str) < 3 or len(clean_str) > 45 or "@" in clean_str:
        return False
        
    # Drop known layout strings instantly
    lower_str = clean_str.lower()
    if lower_str in ['read bio', 'view profile', 'staff', 'team', 'directory', 'board', 'executive', 'members', 'home']:
        return False
        
    # 🛡️ CATCH-ALL GATEWAY: Prevent corporate/initiative directory pollution
    if any(keyword in lower_str for keyword in ORGANIZATION_KEYWORDS):
        return False

    # Check word counts: Human directory names are typically 2 to 4 words (allowing suffix credentials)
    words = clean_str.split()
    if len(words) < 2 or len(words) > 4:
        return False
        
    # Basic character sanitization gate (allowing commas for suffix credentials)
    if not re.match(r"^[a-zA-Z\s\.\,\-\'’]+$", clean_str):
        return False

    # 💎 PARSER LAYER: Let nameparser dissect the layout mechanics
    try:
        parsed = HumanName(clean_str)
        
        # A valid directory name must have at least a first name and a last name
        if not parsed.first or not parsed.last:
            return False
            
    except Exception:
        return False
        
    return True


def parse_name(raw_name):
    """Splits full names cleanly into First and Last using nameparser properties."""
    # Clean up trailing structural punctuation before validating
    clean_name = re.sub(r'[\s,]+(CEO|President|CPA|CCE|MBA|PC|Executive).*$', '', raw_name, flags=re.IGNORECASE).strip()
    
    if not is_valid_human_name(clean_name):
        return "", ""

    parsed = HumanName(clean_name)
    return parsed.first.strip(), parsed.last.strip()


class Command(BaseCommand):
    help = 'Runs the Playwright proximity scraper to collect Chamber leads entirely in memory.'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str, help='Target URL to scrape directly')
        parser.add_argument('--name', type=str, help='Custom Chamber Name')
        parser.add_argument('--state', type=str, help='Target State Focus')

    def handle(self, *args, **options):
        target_url = options.get('url')
        custom_name = options.get('name')
        target_state = options.get('state')

        # Pure in-memory dictionary payload manifestation
        session_results_manifest = {}

        if target_url and custom_name:
            self.stdout.write(self.style.SUCCESS(f"🚀 Routing Dynamic Target Pipeline Execution for {custom_name}..."))
            staged_leads, dynamic_url = self.refactored_chamber_scoper(target_url, custom_name)
            
            session_results_manifest[custom_name] = {
                'directory_url': dynamic_url or target_url,
                'state': target_state if target_state else 'US',
                'leads': staged_leads
            }
        else:
            chamber_market = [
                ('https://metroatlantachamber.com/meet-the-team/', 'Metro Atlanta Chamber', 'GA'),
                ('https://cobbchamber.org/about-us/chamber-staff/', 'Cobb Chamber', 'GA'),
                ('https://www.gwinnettchamber.org/staff/', 'Gwinnett Chamber', 'GA')
            ]
            
            self.stdout.write(self.style.SUCCESS("🚀 Starting Standard Chamber Pipeline Pure Memory Scraper..."))

            for url, name, state in chamber_market:
                staged_leads, dynamic_url = self.refactored_chamber_scoper(url, name)
                session_results_manifest[name] = {
                    'directory_url': dynamic_url or url,
                    'state': state,
                    'leads': staged_leads
                }
                time.sleep(random.uniform(2.0, 4.0))

        self.stdout.write(self.style.SUCCESS("\n🎉 Done! Proximity staging extraction finished."))
        
        for chamber, metrics in session_results_manifest.items():
            self.stdout.write(f"📊 Preview Ready: {chamber} ({len(metrics['leads'])} Staged Vectors Compiled). Payment Status: Pending.")
            
        return json.dumps(session_results_manifest)

    def discover_chamber_url(self, page, google_url):
        """🔍 Sifter Layer: Opens Google, handles consent gates, and pulls back organic results."""
        try:
            page.goto(google_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            
            consent_handled = page.evaluate('''() => {
                let buttons = Array.from(document.querySelectorAll('button, div[role="button"]'));
                let targets = ['accept all', 'i agree', 'agree', 'accept', 'allow all'];
                for (let btn of buttons) {
                    let text = (btn.innerText || btn.textContent || '').toLowerCase().trim();
                    if (targets.includes(text)) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }''')
            
            if consent_handled:
                time.sleep(3)

            links = page.evaluate('''() => {
                let results = [];
                let anchors = Array.from(document.querySelectorAll('a'));
                for (let a of anchors) {
                    let href = a.href;
                    let text = (a.innerText || a.textContent || '').toLowerCase();
                    if (!href) continue;
                    if (href.includes('google.com/url?')) {
                        let match = href.match(/[?&]q=([^&]+)/);
                        if (match) href = decodeURIComponent(match[1]);
                    }
                    if (href.startsWith('http') && !href.includes('google.com')) {
                        results.push({ href: href, text: text });
                    }
                }
                return results;
            }''')
            
            if len(links) == 0:
                match = re.search(r'q=([^&]+)', google_url)
                if match:
                    query = re.sub(r'\+|-', ' ', urllib.parse.unquote(match[1]))
                    clean_query = query.lower().replace('chamber of commerce', '').replace('chamber', '').strip()
                    clean_query = re.sub(r'\b(ca|ga|fl|ny|tx|nc|sc|oh|il|city|regional)\b', '', clean_query).strip()
                    domain_guess = clean_query.replace(' ', '')
                    return f"https://www.{domain_guess}chamber.org"

            for node in links:
                link = node['href']
                text = node['text']
                if any(x in link.lower() for x in ['search?', 'maps.', 'support.', 'accounts.', 'googleusercontent', 'preferences']):
                    continue
                if 'chamber' in link.lower() or 'chamber' in text or 'commerce' in text:
                    return link
                    
            for node in links:
                link = node['href']
                if any(x in link.lower() for x in ['search?', 'maps.', 'support.', 'accounts.', 'googleusercontent', 'preferences']):
                    continue
                return link
        except Exception as e:
            self.stdout.write(f"⚠️ [DISCOVERY]: Sifter index time out: {e}")
        return None

    def crawl_for_directory_target(self, page, base_url):
        """🕷️ Scout Layer: Crawls internal navigation menus to jump straight to team/staff pages."""
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            
            target_page = page.evaluate('''() => {
                let anchors = Array.from(document.querySelectorAll('a'));
                let keywords = ['staff', 'team', 'about-us', 'directory', 'about/staff', 'about/team', 'contact-us'];
                
                let isValidLink = (a) => {
                    let hrefAttr = a.getAttribute('href') || '';
                    return hrefAttr.trim() !== '' && 
                           !hrefAttr.startsWith('#') && 
                           !hrefAttr.startsWith('javascript:') && 
                           a.href && 
                           a.href.startsWith('http');
                };

                for (let kw of keywords) {
                    let match = anchors.find(a => (a.innerText || a.textContent || '').toLowerCase().includes(kw) && isValidLink(a));
                    if (match) return match.href;
                }
                
                for (let kw of keywords) {
                    let match = anchors.find(a => (a.getAttribute('href') || '').toLowerCase().includes(kw) && isValidLink(a));
                    if (match) return match.href;
                }
                return null;
            }''')
            if target_page:
                return target_page
        except Exception as e:
            self.stdout.write(f"⚠️ [SCOUT]: Navigation map scan incomplete: {e}")
        return base_url

    def refactored_chamber_scoper(self, target_url, org_name):
        staged_json_payload = []
        resolved_url = target_url

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--disable-infobars', '--no-sandbox']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )
            page = context.new_page()

            if "google.com/search" in target_url:
                primary_domain = self.discover_chamber_url(page, target_url)
                if primary_domain:
                    resolved_url = self.crawl_for_directory_target(page, primary_domain)
                else:
                    self.stdout.write(self.style.ERROR("❌ [ENGINE ERROR]: Discovery link extraction failed."))
                    browser.close()
                    return staged_json_payload, resolved_url

            # 🎯 STAGE 1: The Navigational Pivot Rescue (Detecting Member Index Traps)
            if any(x in resolved_url.lower() for x in ["member-directory", "members", "directory"]):
                self.stdout.write(self.style.WARNING(f"⚠️ [PIVOT DETECTED]: Target looks like a business roster. Running rescue to internal human coordinates..."))
                try:
                    page.goto(resolved_url, wait_until="domcontentloaded", timeout=30000)
                    rescue_url = page.evaluate('''() => {
                        let links = Array.from(document.querySelectorAll('a'));
                        let targets = ['staff', 'team', 'board of directors', 'board', 'leadership', 'governance', 'about us', 'about'];
                        for (let t of targets) {
                            let found = links.find(a => (a.innerText || a.textContent || '').toLowerCase().includes(t) && !a.href.includes('member-directory') && a.href.startsWith('http'));
                            if (found) return found.href;
                        }
                        return null;
                    }''')
                    if rescue_url:
                        resolved_url = rescue_url
                        self.stdout.write(self.style.SUCCESS(f"🔄 [RESCUE SUCCESS]: Shifted pipeline sweep target to: {resolved_url}"))
                except Exception:
                    pass

            # Double-Attempt Fallback Loop Strategy
            for attempt in range(2):
                if attempt == 1:
                    # 🎯 STAGE 2: If previous coordinates yielded 0, fall back to structural root tree search
                    parsed_uri = urllib.parse.urlparse(resolved_url)
                    fallback_base = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                    self.stdout.write(self.style.WARNING(f"⚠️ [ZERO YIELD FALLBACK]: Attempt 1 hit an empty layer. Rerouting scan back to base root..."))
                    resolved_url = self.crawl_for_directory_target(page, fallback_base)

                self.stdout.write(f"⚙️ [PLAYWRIGHT]: (Attempt {attempt + 1}) Executing layout proximity scoper at: {resolved_url}")
                
                try:
                    page.goto(resolved_url, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(5) 
                    
                    for _ in range(6):
                        page.evaluate("window.scrollBy(0, 800);")
                        time.sleep(0.4)
                    
                    # Exact structural parsing map pulled directly from your working original script
                    extracted_leads = page.evaluate('''() => {
                        let data = [];
                        let seenEmails = new Set();
                        let emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/;
                        
                        let elements = Array.from(document.querySelectorAll('body *')).filter(el => {
                            let txt = el.innerText || el.textContent;
                            return txt && el.children.length === 0 && txt.trim().length > 0;
                        });

                        for (let i = 0; i < elements.length; i++) {
                            let currentText = (elements[i].innerText || elements[i].textContent).trim();
                            let emailMatch = currentText.match(emailRegex);
                            
                            if (emailMatch || (elements[i].tagName === 'A' && elements[i].getAttribute('href') && elements[i].getAttribute('href').startsWith('mailto:'))) {
                                let email = emailMatch ? emailMatch[0].toLowerCase().trim() : elements[i].getAttribute('href').replace('mailto:', '').split('?')[0].toLowerCase().trim();
                                
                                let junk = ["info@", "admin@", "events@", "support@", "frontdesk@", "sales@", "chamber@"];
                                if (seenEmails.has(email) || junk.some(word => email.includes(word))) continue;
                                seenEmails.has(email) ? null : seenEmails.add(email);

                                let rawName = "";
                                let rawTitle = "";
                                
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

                    seen_names = set()

                    for lead in extracted_leads:
                        raw_name = lead['rawName'].strip()
                        title = lead['title'].strip()
                        email = lead['email'].strip()

                        lower_name = raw_name.lower()
                        lower_title = title.lower()

                        if any(keyword in lower_name or keyword in lower_title for keyword in BLACKLIST_KEYWORDS):
                            continue

                        if any(bad in lower_name for bad in ["chamber", "home", "about", "events", "contact", "join", "sign up", "terms", "privacy", "staff"]):
                            continue

                        if email in title:
                            title = title.replace(email, "").strip()

                        first_name, last_name = parse_name(raw_name)
                        full_name = f"{first_name} {last_name}".strip()
                        
                        if not first_name or len(first_name) < 2 or full_name in seen_names:
                            continue
                        seen_names.add(full_name)

                        cleaned_title = title.strip().strip('-').strip(',').replace("  ", " ")
                        if not cleaned_title or cleaned_title.lower() in ["read bio", "view profile", "bio"]:
                            cleaned_title = "Chamber Executive"

                        # 📦 TRANS-MEMORY ARTIFACT ASSEMBLY (Strictly No Database Operations)
                        staged_json_payload.append({
                            'first_name': first_name.strip().title(),
                            'last_name': last_name.strip().title(),
                            'title': cleaned_title,
                            'email': email.lower().strip()
                        })
                        self.stdout.write(f"   ⏳ Staged candidate memory structure: {first_name.title()} {last_name.title()} ({email})")

                    if len(staged_json_payload) > 0:
                        self.stdout.write(self.style.SUCCESS(f"   🔒 Compiled {len(staged_json_payload)} temporary lead vectors securely in-memory."))
                        break  # Breakthrough verified, escape the fallback retry loops!
                    else:
                        self.stdout.write(self.style.WARNING(f"   ⚠️ Proximity extraction attempt hit 0 targets on current path."))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Execution crash on {org_name}: {e}"))
                    
            browser.close()

        return staged_json_payload, resolved_url