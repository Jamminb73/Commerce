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

# 🛡️ IMPORT MATRIX MAP: Maps directly to your local application structure
from leads.models import ChamberLead, ChamberDirectory, ChamberRequest, Order, OrderItem, UserPurchase

# 🛡️ REFACTORED EXTRACTION FILTER MATRIX (Removed 'board of directors' and 'foundation' blockages)
BLACKLIST_KEYWORDS = (
    'camping', 'toll', 'road', 'download', 'pdf', 'excel', 'word', 'powerpoint',
    'trip', 'guide', 'visit', 'follow us', 'our mission', 'privacy policy', 
    'terms of service', 'newsletter', 'copyright', 'explore', 'vacation', 
    'listing', 'advertisement', 'heritage', 'gallery', 'history'
)

GENERIC_BOXES = ('info@', 'support@', 'admin@', 'marketing@', 'contact@', 'webmaster@', 'help@', 'membership@', 'events@', 'join@', 'chamber@', 'frontdesk@', 'sales@')

ORGANIZATION_KEYWORDS = (
    'business', 'center', 'visitor', 'council', 'service', 'chamber', 'association',
    'alliance', 'bureau', 'corporation', 'company', 'inc.', 'llc', 'group', 'dept',
    'department', 'practices', 'committee', 'development', 'partnership', 'network', 
    'agency', 'institute', 'society', 'club'
)

STAFF_PAGE_HINTS = ('staff', 'team', 'leadership', 'board', 'executive', 'people', 'directory', 'officers', 'employee')
LOW_SIGNAL_PAGES = ('event', 'events', 'news', 'blog', 'gallery', 'history', 'privacy', 'terms', 'download', 'guide', 'visit', 'vacation')


def is_valid_human_name(name_str):
    """Rigorously validates if a string is structured like an actual human name."""
    if not name_str:
        return False
        
    clean_str = name_str.strip()
    if len(clean_str) < 3 or len(clean_str) > 45 or "@" in clean_str:
        return False
        
    lower_str = clean_str.lower()
    if lower_str in ['read bio', 'view profile', 'staff', 'team', 'directory', 'members', 'home']:
        return False
        
    if any(keyword in lower_str for keyword in ORGANIZATION_KEYWORDS):
        return False

    words = clean_str.split()
    if len(words) < 2 or len(words) > 4:
        return False
        
    if not re.match(r"^[a-zA-Z\s\.\,\-\'’]+$", clean_str):
        return False

    try:
        parsed = HumanName(clean_str)
        if not parsed.first or not parsed.last:
            return False
    except Exception:
        return False
        
    return True


def parse_name(raw_name):
    """Splits full names cleanly into First and Last using nameparser properties."""
    clean_name = re.sub(r'[\s,]+(CEO|President|CPA|CCE|MBA|PC|Executive).*$', '', raw_name, flags=re.IGNORECASE).strip()
    if not is_valid_human_name(clean_name):
        return "", ""
    parsed = HumanName(clean_name)
    return parsed.first.strip(), parsed.last.strip()


def predict_b2b_email(first_name, last_name, company_name):
    """Reconstructs highly probable B2B emails using company domain heuristics."""
    if not first_name or not last_name:
        return "member@chamber-roster.org"
        
    clean_co = company_name.lower().strip()
    clean_co = re.sub(r'[\s,]+(inc\.|inc|llc|gmbh|co\.|co|corp\.|corporation|group|center|association|club|system|bank)\b', '', clean_co)
    clean_co = re.sub(r'[^a-z0-9]', '', clean_co)
    
    if not clean_co or len(clean_co) < 3:
        clean_co = "corporate-hub"
        
    domain = f"{clean_co}.com"
    f = first_name.lower().strip()
    l = last_name.lower().strip()
    
    return f"{f}.{l}@{domain}"


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

    def crawl_for_directory_target(self, page, base_url, exclude_urls=None):
        """🕷️ Intent Scout Layer: Scores navigation text globally to unmask high-value hidden targets."""
        if exclude_urls is None:
            exclude_urls = []
            
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state('networkidle', timeout=15000)
            time.sleep(4)  
            
            target_page = page.evaluate('''([baseUrl, blacklistedPaths]) => {
                let elements = Array.from(document.querySelectorAll('a, [data-href], [data-url], [aria-controls], li, button'));
                let bestLink = null;
                let highestScore = -999;

                let cleanUrlString = (str) => {
                    if (!str) return '';
                    let clean = str.toLowerCase().trim();
                    if (clean.endsWith('/')) {
                        clean = clean.slice(0, -1);
                    }
                    return clean;
                };

                let preparedBlacklist = blacklistedPaths.map(url => cleanUrlString(url));

                // Semantic Priority Weights
                let scoringMatrix = [
                    { keywords: ['board of directors', 'board roster', 'governance', 'board-of-directors'], score: 140 },
                    { keywords: ['chamber staff', 'meet the team', 'our team', 'staff directory', 'chamber-staff', 'leadership team'], score: 130 },
                    { keywords: ['staff', 'leadership', 'executive committee', 'executive', 'people', 'officers', 'board'], score: 110 },
                    { keywords: ['directory', 'about us', 'about-us', 'contact'], score: 45 }
                ];

                for (let el of elements) {
                    let rawHref = el.getAttribute('href') || el.getAttribute('data-href') || el.getAttribute('data-url') || '';
                    if (!rawHref || rawHref.startsWith('#') || rawHref.startsWith('javascript:')) continue;

                    let fullUrl = '';
                    try {
                        fullUrl = new URL(rawHref, baseUrl).href;
                    } catch(e) {
                        continue;
                    }

                    let normalizedCurrentUrl = cleanUrlString(fullUrl);
                    if (preparedBlacklist.some(badUrl => normalizedCurrentUrl === badUrl)) {
                        continue;
                    }
                    
                    let text = (el.innerText || el.textContent || '').toLowerCase().trim();
                    let hrefAttrLower = rawHref.toLowerCase();
                    let pathHint = (window.location.pathname || '').toLowerCase();
                    
                    let currentScore = 0;
                    let matchedAny = false;
                    
                    for (let rule of scoringMatrix) {
                        if (rule.keywords.some(kw => text.includes(kw) || hrefAttrLower.includes(kw))) {
                            currentScore = Math.max(currentScore, rule.score);
                            matchedAny = true;
                        }
                    }

                    if (pathHint.includes('/staff') || pathHint.includes('/team') || pathHint.includes('/leadership') || pathHint.includes('/board') || pathHint.includes('/people') || pathHint.includes('/directory')) {
                        currentScore += 20;
                    }

                    if (text.includes('program') || hrefAttrLower.includes('program') || text.includes('events') || hrefAttrLower.includes('events') || text.includes('workshop') || hrefAttrLower.includes('workshop')) {
                        currentScore -= 90;
                    }

                    if (matchedAny && currentScore > highestScore) {
                        highestScore = currentScore;
                        bestLink = fullUrl;
                    }
                }
                
                return bestLink;
            }''', [base_url, exclude_urls])
            
            if target_page:
                return target_page
        except Exception as e:
            self.stdout.write(f"⚠️ [SCOUT]: Navigation link scoring sweep hit an issue: {e}")
        return base_url

    def build_candidate_urls(self, base_url):
        """Build a small list of likely staff/directory URLs to retry when the first page is sparse."""
        candidates = []
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            return candidates

        base = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.rstrip('/')
        path_variants = [
            '',
            '/staff/',
            '/team/',
            '/leadership/',
            '/about-us/',
            '/about/',
            '/directory/',
            '/members/',
            '/people/',
            '/contact/'
        ]

        for variant in path_variants:
            if variant == '':
                candidates.append(base)
            else:
                candidates.append(base + variant)

        if path:
            for variant in ('/staff/', '/team/', '/leadership/', '/directory/', '/people/'):
                candidates.append(base + path + variant)
            candidates.append(base + path)

        seen = set()
        ordered = []
        for url in candidates:
            if url not in seen:
                seen.add(url)
                ordered.append(url)
        return ordered

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

            # 🎯 STAGE 1: Navigational Shift (Avoid member search widgets, hunt for human listings)
            if any(x in resolved_url.lower() for x in ["member-directory", "members", "directory"]):
                self.stdout.write(self.style.WARNING(f"⚠️ [PIVOT DETECTED]: Target path points to business listings. Scouting leadership targets..."))
                try:
                    page.goto(resolved_url, wait_until="domcontentloaded", timeout=30000)
                    rescue_url = page.evaluate('''() => {
                        let links = Array.from(document.querySelectorAll('a'));
                        let targets = ['board of directors', 'board', 'staff', 'team', 'leadership', 'governance', 'about us'];
                        for (let t of targets) {
                            let found = links.find(a => (a.innerText || a.textContent || '').toLowerCase().includes(t) && !a.href.includes('member-directory') && a.href.startsWith('http'));
                            if (found) return found.href;
                        }
                        return null;
                    }''')
                    if rescue_url:
                        resolved_url = rescue_url
                        self.stdout.write(self.style.SUCCESS(f"🔄 [RESCUE SUCCESS]: Redirected search route to high-signal layout: {resolved_url}"))
                except Exception:
                    pass

            # Track unique attempted routes to prevent duplication loops
            attempted_urls = []
            candidate_urls = self.build_candidate_urls(resolved_url)

            for attempt in range(3):
                current_url = resolved_url
                if attempt == 1:
                    parsed_uri = urllib.parse.urlparse(resolved_url)
                    fallback_base = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                    self.stdout.write(self.style.WARNING(f"⚠️ [ZERO YIELD FALLBACK]: Attempt 1 hit an empty extraction layer. Retrying root routing map..."))
                    attempted_urls.append(resolved_url)
                    current_url = self.crawl_for_directory_target(page, fallback_base, exclude_urls=attempted_urls)
                elif attempt == 2 and candidate_urls:
                    for candidate in candidate_urls:
                        clean_cand = candidate.rstrip('/')
                        clean_att = [u.rstrip('/') for u in attempted_urls]
                        if clean_cand not in clean_att and candidate != current_url:
                            current_url = candidate
                            break
                    self.stdout.write(self.style.WARNING(f"⚠️ https://www.merriam-webster.com/dictionary/retry: Attempt 3 switching to candidate route: {current_url}"))

                resolved_url = current_url
                self.stdout.write(f"⚙️ [PLAYWRIGHT]: (Attempt {attempt + 1}) Executing layout proximity scoper at: {resolved_url}")

                try:
                    page.goto(resolved_url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_load_state('networkidle', timeout=15000)
                    time.sleep(3)

                    for _ in range(6):
                        page.evaluate("window.scrollBy(0, 800);")
                        time.sleep(0.4)

                    page_summary = page.evaluate('''() => {
                        const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
                        const text = (value) => (value || '').replace(/\s+/g, ' ').trim();
                        const bodyText = text(document.body ? document.body.innerText || document.body.textContent : '');
                        const mailtoCount = document.querySelectorAll('a[href^="mailto:"]').length;
                        const dataEmailCount = document.querySelectorAll('[data-email]').length;
                        const emailTextMatches = bodyText.match(emailRegex) || [];
                        const pageUrl = window.location.href || '';
                        const likelyStaff = /(staff|team|leadership|directory|board|executive|people|officers|members|employee)/i.test(bodyText + ' ' + document.title + ' ' + pageUrl) || /(\/staff\/|\/team\/|\/leadership\/|\/board\/|\/people\/|\/directory\/)/i.test(pageUrl);
                        return {
                            title: document.title || '',
                            url: window.location.href,
                            mailtoCount,
                            dataEmailCount,
                            emailTextMatches: emailTextMatches.length,
                            wordCount: bodyText.split(/\s+/).filter(Boolean).length,
                            likelyStaff
                        };
                    }''')

                    is_likely_staff_page = page_summary.get('likelyStaff', False)

                    self.stdout.write(
                        f"📈 [SCAN] URL={page_summary.get('url', resolved_url)} | "
                        f"Title={page_summary.get('title', 'N/A')} | "
                        f"mailto={page_summary.get('mailtoCount', 0)} | "
                        f"data-email={page_summary.get('dataEmailCount', 0)} | "
                        f"email-text={page_summary.get('emailTextMatches', 0)} | "
                        f"likely-staff={is_likely_staff_page}"
                    )

                    # Pass control argument down to JavaScript evaluation scope mapping context
                    extracted_leads = page.evaluate('''([forceRosterHarvest]) => {
                        let data = [];
                        let seenEmails = new Set();
                        let emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
                        let junk = ["info@", "admin@", "events@", "support@", "frontdesk@", "sales@", "chamber@", "webmaster@", "membership@"];
                        let text = (value) => (value || '').replace(/\s+/g, ' ').trim();

                        // --- PASS 1: STANDARD DIRECT EMAIL HARVESTER ---
                        let mailtoAnchors = Array.from(document.querySelectorAll('a[href^="mailto:"]'));
                        let attrAnchors = Array.from(document.querySelectorAll('a[href], [data-email], [data-href]'))
                            .filter(el => {
                                let href = (el.getAttribute('href') || el.getAttribute('data-href') || '').toLowerCase();
                                let dataEmail = (el.getAttribute('data-email') || '').toLowerCase();
                                return href.includes('@') || dataEmail.includes('@');
                            });

                        if (mailtoAnchors.length === 0) {
                            let allElements = Array.from(document.querySelectorAll('body *'));
                            for (let el of allElements) {
                                let textContent = text(el.innerText || el.textContent || '');
                                let match = textContent.match(emailRegex);
                                if (match) {
                                    let email = match[0].toLowerCase();
                                    if (!junk.some(word => email.includes(word))) {
                                        let mockAnchor = document.createElement('a');
                                        mockAnchor.setAttribute('href', 'mailto:' + email);
                                        el.appendChild(mockAnchor);
                                        mailtoAnchors.push(mockAnchor);
                                    }
                                }
                            }
                        }

                        let candidateAnchors = mailtoAnchors.concat(attrAnchors);
                        let anchorSet = [];
                        for (let anchor of candidateAnchors) {
                            let email = '';
                            let href = (anchor.getAttribute('href') || anchor.getAttribute('data-href') || '').trim();
                            let dataEmail = (anchor.getAttribute('data-email') || '').trim();
                            if (href.startsWith('mailto:')) {
                                email = href.replace('mailto:', '').split('?')[0].toLowerCase().trim();
                            } else if (dataEmail) {
                                email = dataEmail.toLowerCase().trim();
                            } else if (href.includes('@')) {
                                email = href.split(/[?#]/)[0].toLowerCase().trim();
                            }
                            if (email && !seenEmails.has(email) && !junk.some(word => email.includes(word)) && email.match(emailRegex)) {
                                seenEmails.add(email);
                                anchorSet.push({ anchor, email });
                            }
                        }

                        for (let item of anchorSet) {
                            let anchor = item.anchor;
                            let email = item.email;
                            let rawName = '';
                            let rawTitle = '';

                            let currentParent = anchor.parentElement;
                            let cardContainer = null;
                            for (let depth = 0; depth < 6; depth++) {
                                if (!currentParent || currentParent.tagName === 'BODY') break;
                                let className = (currentParent.className || '').toLowerCase();
                                let idName = (currentParent.id || '').toLowerCase();
                                if (className.includes('card') || className.includes('member') || className.includes('staff') ||
                                    className.includes('team') || className.includes('profile') || className.includes('person') ||
                                    className.includes('employee') || className.includes('row') || className.includes('block') ||
                                    className.includes('item') || idName.includes('user') || idName.includes('person')) {
                                    cardContainer = currentParent;
                                    break;
                                }
                                currentParent = currentParent.parentElement;
                            }

                            if (!cardContainer) {
                                let closest = anchor.closest('article, section, li, tr, div, td, p');
                                if (closest) cardContainer = closest;
                            }

                            if (cardContainer) {
                                let cardTextNodes = Array.from(cardContainer.querySelectorAll('*'))
                                    .filter(el => el.children.length === 0)
                                    .map(el => text(el.innerText || el.textContent || ''))
                                    .filter(txt => txt.length > 1 && !emailRegex.test(txt) && !txt.toLowerCase().includes('bio') && !txt.toLowerCase().includes('profile'));

                                let headingCandidates = Array.from(cardContainer.querySelectorAll('h1,h2,h3,h4,strong'))
                                    .map(el => text(el.innerText || el.textContent || ''))
                                    .filter(txt => txt.length > 2 && !emailRegex.test(txt) && txt.split(/\s+/).length <= 6)
                                    .filter(txt => !/(contact us|about us|read bio|view profile|bio|follow us|subscribe|join us)/i.test(txt));

                                if (cardTextNodes.length >= 2) {
                                    rawName = cardTextNodes[0];
                                    rawTitle = cardTextNodes[1];
                                } else if (headingCandidates.length >= 2) {
                                    rawName = headingCandidates[0];
                                    rawTitle = headingCandidates[1];
                                } else if (cardTextNodes.length === 1) {
                                    rawName = cardTextNodes[0];
                                } else if (headingCandidates.length === 1) {
                                    rawName = headingCandidates[0];
                                }
                            }

                            if (!rawName || rawName.length < 3) {
                                let allLeafs = Array.from(document.querySelectorAll('body *')).filter(el => el.children.length === 0);
                                let idx = allLeafs.indexOf(anchor);
                                if (idx === -1) {
                                    idx = allLeafs.findIndex(el => el.contains(anchor) || anchor.contains(el));
                                }
                                if (idx !== -1) {
                                    let lookbackCount = 0;
                                    for (let j = idx - 1; j >= 0 && lookbackCount < 7; j--) {
                                        let candidateText = text(allLeafs[j].innerText || allLeafs[j].textContent || '');
                                        if (!candidateText || candidateText.length < 2 || emailRegex.test(candidateText) || /\d{3}/.test(candidateText) || candidateText.toLowerCase().includes('bio')) continue;
                                        if (!rawName && candidateText !== rawTitle) {
                                            rawName = candidateText;
                                        } else if (!rawTitle) {
                                            rawTitle = candidateText;
                                            break;
                                        }
                                        lookbackCount++;
                                    }
                                }
                            }

                            if (rawName && rawName.length >= 3) {
                                let cleanName = rawName.replace(/\s+/g, ' ').trim();
                                let cleanTitle = (rawTitle || '').replace(/\s+/g, ' ').trim();
                                let lowerName = cleanName.toLowerCase();
                                let lowerTitle = cleanTitle.toLowerCase();

                                if (/(contact|about|home|join|events|members|directory|team|staff|subscribe|view profile|read bio)/i.test(lowerName) ||
                                    /(contact|about|home|join|events|members|directory|team|staff|subscribe|view profile|read bio)/i.test(lowerTitle)) {
                                    continue;
                                }

                                data.push({ rawName: cleanName, title: cleanTitle || 'Chamber Executive', email });
                            }
                        }

                        // --- PASS 2: wired `likelyStaff` ACTUATOR ACTIVATION GATE ---
                        if (data.length === 0 && forceRosterHarvest) {
                            let nameHeaders = Array.from(document.querySelectorAll('h2, h3, h4, strong')).filter(el => {
                                let val = text(el.innerText || el.textContent || '');
                                return val.length >= 3 && val.length <= 40 && val.includes(' ');
                            });

                            for (let heading of nameHeaders) {
                                let rawName = text(heading.innerText || heading.textContent || '');
                                let rawTitle = '';
                                let companyText = '';

                                let currentSibling = heading.nextElementSibling;
                                let limit = 0;
                                while (currentSibling && limit < 3) {
                                    let siblingText = text(currentSibling.innerText || currentSibling.textContent || '');
                                    if (siblingText && siblingText.length > 2 && !siblingText.includes('subscribe') && !siblingText.includes('view')) {
                                        if (!rawTitle) {
                                            rawTitle = siblingText;
                                        } else {
                                            companyText = siblingText;
                                            break;
                                        }
                                    }
                                    currentSibling = currentSibling.nextElementSibling;
                                    limit++;
                                }

                                if (rawName && rawName.length >= 3) {
                                    let fullTitleString = rawTitle;
                                    if (companyText) {
                                        fullTitleString += " - " + companyText;
                                    }
                                    data.push({
                                        rawName: rawName,
                                        title: fullTitleString || 'Chamber Board Director',
                                        email: 'GENERATE_B2B_MATRIX'
                                    });
                                }
                            }
                        }
                        return data;
                    }''', [is_likely_staff_page])

                    seen_names = set()

                    for lead in extracted_leads:
                        raw_name = lead['rawName'].strip()
                        title = lead['title'].strip()
                        email = lead['email'].strip()

                        lower_name = raw_name.lower()
                        lower_title = title.lower()

                        if any(keyword in lower_name or keyword in lower_title for keyword in BLACKLIST_KEYWORDS):
                            continue

                        if any(bad in lower_name for bad in ["chamber", "home", "about", "events", "contact", "join", "sign up", "terms", "privacy"]):
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

                        if email == 'GENERATE_B2B_MATRIX':
                            company_hint = cleaned_title.split('-')[-1].strip() if '-' in cleaned_title else org_name
                            email = predict_b2b_email(first_name, last_name, company_hint)

                        staged_json_payload.append({
                            'first_name': first_name.strip().title(),
                            'last_name': last_name.strip().title(),
                            'title': cleaned_title,
                            'email': email.lower().strip()
                        })
                        self.stdout.write(f"   ⏳ Staged candidate memory structure: {first_name.title()} {last_name.title()} ({email})")

                    if len(staged_json_payload) > 0:
                        self.stdout.write(self.style.SUCCESS(f"   🔒 Compiled {len(staged_json_payload)} temporary lead vectors securely in-memory."))
                        break 
                    else:
                        self.stdout.write(self.style.WARNING(f"   ⚠️ Proximity extraction attempt hit 0 targets on current path."))
                        attempted_urls.append(resolved_url)

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Execution crash on {org_name}: {e}"))

            browser.close()

        return staged_json_payload, resolved_url