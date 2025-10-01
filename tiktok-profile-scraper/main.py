import re
import time
import random
import json
import datetime
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
# import undetected_chromedriver as uc  # 문제가 있어 일반 Selenium만 사용

# 🔐 틱톡 쿠키와 로컬 스토리지를 외부 파일에서 로드
def load_cookies():
    try:
        with open('cookies.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️ cookies.json 파일을 찾을 수 없습니다. 기본 쿠키를 사용합니다.")
        # 기본 쿠키 정보 (백업용)
        return [
            {"name": "sessionid", "value": "a40d3c265d440d5daa789f1ab45d96f3", "domain": ".tiktok.com"},
            {"name": "sid_tt", "value": "a40d3c265d440d5daa789f1ab45d96f3", "domain": ".tiktok.com"}
            # 나머지 기본 쿠키는 생략
        ]

def load_local_storage():
    try:
        with open('local_storage.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️ local_storage.json 파일을 찾을 수 없습니다. 기본 값을 사용합니다.")
        # 기본 로컬 스토리지 정보 (백업용)
        return {
            "SLARDARtiktok_webapp": "JTdCJTIydXNlcklkJTIyOiUyMjc0ODkwNzQ5MDM4NjI3NDA0OTclMjIsJTIyZGV2aWNlSWQlMjI6JTIyMjhkYWRjYjQtMDZlZi00ZjYwLTgxMWQtMzM1NDM3OTNiZmFmJTIyLCUyMmV4cGlyZXMlMjI6MTc1NTI0MjIxNDQ5NCU3RA==",
            "SLARDARtiktok_webapp_login": "JTdCJTIydXNlcklkJTIyOiUyMjc0ODkwNzQ5MDM4NjI3NDA0OTclMjIsJTIyZGV2aWNlSWQlMjI6JTIyNWRjODMwYjctNzZmZS00NDY4LWE0MWUtMGFlZDM5YWNiYTk5JTIyLCUyMmV4cGlyZXMlMjI6MTc1NTI0MjIwNjUzMyU3RA==",
            "__tea_cache_tokens_1988": "{\"web_id\":\"7489074903862740497\",\"user_unique_id\":\"7489074903862740497\",\"timestamp\":1747466214846,\"_type_\":\"default\"}"
        }

# 쿠키와 로컬 스토리지 로드
cookies = load_cookies()
local_storage_items = load_local_storage()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:94.0) Gecko/20100101 Firefox/94.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0"
]

def random_sleep(min_sec=1, max_sec=3):
    """인간과 비슷한 불규칙적 대기 시간 생성"""
    sleep_time = random.uniform(min_sec, max_sec)
    print(f"⏱️ {sleep_time:.2f}초 대기 중...")
    time.sleep(sleep_time)

def check_cookie_expiry():
    """쿠키 만료 확인 및 경고"""
    # 쿠키 만료일 확인 (2025-11-13 기준)
    expiry_date = datetime.datetime(2025, 11, 13)
    today = datetime.datetime.now()
    days_left = (expiry_date - today).days
    
    if days_left < 30:
        print(f"⚠️ 주의: 쿠키가 {days_left}일 후에 만료됩니다. 새로운 쿠키를 준비하세요.")
    
    return days_left

def setup_driver():
    """셀레니움 드라이버 설정 및 쿠키 적용"""
    # 쿠키 만료 확인
    days_left = check_cookie_expiry()
    print(f"🔐 쿠키 상태 확인: 만료까지 {days_left}일 남음")
    
    # 일반 셀레늄 사용
    print("🌐 셀레늄 크롬드라이버 초기화 중...")
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    user_agent = random.choice(USER_AGENTS)
    print(f"🔄 무작위 User-Agent 선택: {user_agent[:30]}...")
    options.add_argument(f"user-agent={user_agent}")
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    # 봇 감지 우회를 위한 추가 옵션
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("✅ 크롬드라이버 초기화 성공")
        
        # 기본 페이지 로드
        print("🌐 틱톡 기본 페이지 로드 중...")
        driver.get("https://www.tiktok.com")
        random_sleep(2, 4)
        
        # 자바스크립트 실행으로 bot 감지 우회 (직접 실행)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # 로컬 스토리지 설정
        print("🔧 로컬 스토리지 설정 중...")
        for key, value in local_storage_items.items():
            driver.execute_script(f"localStorage.setItem('{key}', '{value}');")
        
        # 쿠키 설정 전에 스토리지 초기화
        driver.execute_script("window.localStorage.clear()")
        driver.execute_script("window.sessionStorage.clear()")
        
        # 사람처럼 마우스 움직임
        driver.execute_script("document.body.dispatchEvent(new MouseEvent('mousemove', {'clientX': 100, 'clientY': 100}))")
        
        # 쿠키 추가
        print("🍪 쿠키 설정 중...")
        success_count = 0
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
                success_count += 1
            except Exception as e:
                print(f"🔴 쿠키 추가 실패 ({cookie['name']}): {e}")
        
        print(f"✅ 쿠키 {success_count}/{len(cookies)}개 성공적으로 설정됨")
        
        # 페이지 새로고침으로 쿠키 적용
        print("🔄 페이지 새로고침으로 쿠키 적용 중...")
        driver.refresh()
        random_sleep(2, 3)
        
        return driver
    except WebDriverException as e:
        print(f"🔴 드라이버 설정 중 오류 발생: {e}")
        # 실패한 경우 드라이버 정리
        try:
            driver.quit()
        except:
            pass
        raise

def extract_email_from_user(username):
    """틱톡 사용자 프로필에서 이메일 추출"""
    url = f"https://www.tiktok.com/@{username}"
    print(f"\n{'='*50}")
    print(f"📱 계정 분석 시작: @{username}")
    print(f"{'='*50}")
    
    driver = None
    try:
        # 드라이버 설정
        driver = setup_driver()
        emails = []

        # 프로필 페이지 접속
        print(f"🔍 프로필 URL 접속 중: {url}")
        driver.get(url)
        random_sleep(4, 6)
        
        # 페이지 로드 확인
        page_title = driver.title
        print(f"📄 페이지 제목: {page_title}")
        
        if "Page Not Found" in page_title or "찾을 수 없음" in page_title:
            print(f"⚠️ 사용자를 찾을 수 없음: @{username}")
            return None
        
        # 접속 후 인간스러운 스크롤 동작
        print("🖱️ 자연스러운 스크롤 동작 시뮬레이션 중...")
        for i in range(3):
            scroll_height = random.randint(100, 300)
            driver.execute_script(f"window.scrollTo(0, {scroll_height});")
            random_sleep(0.5, 1.5)
        
        # 다양한 방법으로 이메일 검색
        try:
            # 1. 프로필 설명 확인
            print("🔍 프로필 설명에서 이메일 검색 중...")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-e2e='user-bio'], [data-e2e='user-page-header']"))
            )
            bio_elements = driver.find_elements(By.CSS_SELECTOR, "[data-e2e='user-bio'], [data-e2e='user-page-header']")
            
            if bio_elements:
                print(f"✅ 프로필 요소 {len(bio_elements)}개 발견")
                bio_text = " ".join([el.text for el in bio_elements])
                print(f"📝 프로필 텍스트: {bio_text[:100]}..." if len(bio_text) > 100 else f"📝 프로필 텍스트: {bio_text}")
                bio_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", bio_text)
                if bio_emails:
                    print(f"✅ 프로필에서 이메일 {len(bio_emails)}개 발견: {bio_emails}")
                    emails.extend(bio_emails)
                else:
                    print("⚠️ 프로필에서 이메일을 찾을 수 없음")
            else:
                print("⚠️ 프로필 요소를 찾을 수 없음")
            
            # 2. 링크 확인 (링크드인, 비즈니스 이메일 등)
            print("🔍 mailto: 링크 검색 중...")
            link_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='mailto:']")
            if link_elements:
                print(f"✅ mailto: 링크 {len(link_elements)}개 발견")
                for link in link_elements:
                    href = link.get_attribute('href')
                    if href and 'mailto:' in href:
                        email = href.replace('mailto:', '')
                        print(f"📧 mailto 링크에서 이메일 발견: {email}")
                        emails.append(email)
            else:
                print("⚠️ mailto: 링크를 찾을 수 없음")
            
            # 3. 추가: 소셜 링크 확인
            print("🔍 소셜 미디어 링크 검색 중...")
            social_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='instagram.com'], a[href*='twitter.com'], a[href*='facebook.com']")
            if social_links:
                social_hrefs = [link.get_attribute('href') for link in social_links]
                print(f"💡 소셜 링크 {len(social_links)}개 발견: {social_hrefs}")
                # (소셜 미디어 스크래핑 코드 추가 가능)
            else:
                print("⚠️ 소셜 미디어 링크를 찾을 수 없음")
            
            # 4. 백업: 클릭 가능한 모든 링크 분석
            print("🔍 연락처 관련 링크 검색 중...")
            all_links = driver.find_elements(By.TAG_NAME, "a")
            contact_links = []
            for link in all_links:
                href = link.get_attribute('href')
                if href and ('contact' in href.lower() or 'about' in href.lower()):
                    contact_links.append(href)
            
            if contact_links:
                print(f"💡 연락처 관련 링크 {len(contact_links)}개 발견: {contact_links}")
            else:
                print("⚠️ 연락처 관련 링크를 찾을 수 없음")
            
        except TimeoutException:
            print("⚠️ 페이지 요소를 찾는 시간이 초과되었습니다.")
        
        # 5. 백업 방법: 페이지 소스에서 직접 검색
        print("🔍 페이지 소스에서 이메일 패턴 검색 중...")
        page_source = driver.page_source
        source_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", page_source)
        if source_emails:
            print(f"✅ 페이지 소스에서 이메일 {len(source_emails)}개 발견")
            for email in source_emails:
                if email not in emails:  # 중복 방지
                    print(f"📧 페이지 소스에서 이메일 발견: {email}")
            emails.extend(source_emails)
        else:
            print("⚠️ 페이지 소스에서 이메일을 찾을 수 없음")
        
        # 6. 숨겨진 이메일 형식 검사 (예: "이메일: user [at] domain [dot] com")
        print("🔍 숨겨진 이메일 형식 검색 중...")
        obscured_pattern = r'\b[a-zA-Z0-9_.+-]+\s*[\[\(]at[\]\)]\s*[a-zA-Z0-9-]+\s*[\[\(]dot[\]\)]\s*[a-zA-Z0-9-.]+\b'
        obscured_matches = re.findall(obscured_pattern, page_source, re.IGNORECASE)
        
        if obscured_matches:
            print(f"✅ 숨겨진 이메일 형식 {len(obscured_matches)}개 발견")
            for match in obscured_matches:
                clean_email = match.replace('[at]', '@').replace('(at)', '@').replace('[dot]', '.').replace('(dot)', '.')
                clean_email = re.sub(r'\s+', '', clean_email)
                if '@' in clean_email and '.' in clean_email:
                    print(f"📧 숨겨진 이메일 형식에서 추출: {clean_email}")
                    emails.append(clean_email)
        else:
            print("⚠️ 숨겨진 이메일 형식을 찾을 수 없음")
        
        # 중복 제거 및 정리
        unique_emails = list(set(emails))
        if unique_emails:
            print(f"✅ 최종 이메일 {len(unique_emails)}개 발견: {unique_emails}")
        else:
            print("⚠️ 이메일을 찾을 수 없었습니다.")
            
        return unique_emails if unique_emails else None

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        print("📋 상세 오류 정보:")
        traceback.print_exc()
        return None
    finally:
        if driver:
            print("🔄 드라이버 종료 중...")
            driver.quit()
        print(f"{'='*50}")
        print(f"📱 계정 분석 완료: @{username}")
        print(f"{'='*50}\n")

def save_results(username, emails):
    """결과를 JSON 파일로 저장"""
    result = {
        "username": username,
        "emails": emails,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cookie_days_left": check_cookie_expiry()
    }
    
    filename = "tiktok_emails.json"
    
    try:
        # 기존 파일 읽기
        with open(filename, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"💾 새 결과 파일 생성: {filename}")
        data = []
    
    # 새 결과 추가
    data.append(result)
    
    # 파일 저장
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"💾 결과가 {filename}에 저장되었습니다.")

# 예시 실행
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔍 틱톡 이메일 스크래퍼 시작")
    print("="*60)
    print(f"🔐 쿠키 만료까지 남은 기간: {check_cookie_expiry()}일")
    
    # 사용자 목록 설정
    usernames = [
        '@amycj93',
        '@gingerswatches',
        '@isabellaalexandra3',
        '@kanashaxtaje',
        '@karlaspringa2',
        '@katekzzzz',
        '@kenyamedole',
        '@prettyblkginl'
    ]
    
    print(f"📋 처리할 계정 수: {len(usernames)}개")
    
    # 결과 저장용 딕셔너리
    results = {}
    success_count = 0
    
    # 각 사용자 처리
    for i, username in enumerate(usernames, 1):
        username = username.strip('@')  # @ 기호 제거
        print(f"\n⏳ 진행 상황: {i}/{len(usernames)} ({i/len(usernames)*100:.1f}%)")
        print(f"👤 현재 처리 중: @{username}")
        
        try:
            result = extract_email_from_user(username)
            if result:
                print(f"✅ 성공: @{username}에서 이메일 {len(result)}개 발견")
                results[username] = result
                save_results(username, result)
                success_count += 1
            else:
                print(f"⚠️ 실패: @{username}에서 이메일을 찾을 수 없음")
                results[username] = []
                
            # IP 차단 방지를 위한 대기
            if i < len(usernames):  # 마지막 계정이 아닌 경우에만 대기
                wait_time = random.randint(15, 30)
                print(f"⏱️ IP 차단 방지를 위해 {wait_time}초 대기 중...")
                time.sleep(wait_time)
                
        except Exception as e:
            print(f"❌ 처리 중 오류 발생: {e}")
            results[username] = f"오류: {str(e)}"
    
    # 결과 요약
    print("\n" + "="*60)
    print("📊 스크래핑 결과 요약")
    print("="*60)
    print(f"✅ 성공: {success_count}/{len(usernames)} 계정 ({success_count/len(usernames)*100:.1f}%)")
    print(f"❌ 실패: {len(usernames) - success_count}/{len(usernames)} 계정 ({(len(usernames) - success_count)/len(usernames)*100:.1f}%)")
    print("\n📧 발견된 이메일 목록:")
    
    for username, emails in results.items():
        if isinstance(emails, list):
            email_status = f"{len(emails)}개 발견: {emails}" if emails else "이메일 없음"
        else:
            email_status = emails  # 오류 메시지
        print(f"  • @{username}: {email_status}")
    
    print("\n✅ 프로그램 종료")
    print("📝 참고: 틱톡 쿠키는 대략 6개월마다 갱신이 필요합니다.")
    print("💡 팁: IP 차단을 피하려면 하루에 10-15개 계정만 스크래핑하세요.")