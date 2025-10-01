import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import os
import ssl
import certifi
from datetime import datetime

# SSL 인증서 문제 해결
ssl._create_default_https_context = ssl._create_unverified_context

class TikTokHashtagScraper:
    def __init__(self):
        self.setup_driver()
        self.collected_data = self.load_collected_data()
        
    def setup_driver(self):
        """크롬 드라이버 설정"""
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--lang=en")
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        
        self.driver = uc.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)
        
        # 쿠키 로드 및 적용
        self.load_cookies()

    def load_collected_data(self):
        """이전에 수집된 데이터 로드"""
        try:
            if os.path.exists("collected_data.json"):
                with open("collected_data.json", "r", encoding='utf-8') as f:
                    return json.load(f)
            return {"hashtags": {}}
        except Exception as e:
            print(f"이전 데이터 로드 중 오류 발생: {str(e)}")
            return {"hashtags": {}}

    def save_collected_data(self):
        """수집된 데이터 저장"""
        try:
            with open("collected_data.json", "w", encoding='utf-8') as f:
                json.dump(self.collected_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"데이터 저장 중 오류 발생: {str(e)}")
            
    def load_cookies(self):
        """저장된 쿠키 로드 및 적용"""
        try:
            self.driver.get("https://www.tiktok.com")
            time.sleep(3)
            
            if os.path.exists("cookies.json"):
                with open("cookies.json", "r") as f:
                    cookies = json.load(f)
                    
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        print(f"쿠키 적용 중 오류 발생: {str(e)}")
                        continue
                
                self.driver.refresh()
                time.sleep(3)
            else:
                print("cookies.json 파일을 찾을 수 없습니다.")
        except Exception as e:
            print(f"쿠키 로드 중 오류 발생: {str(e)}")
            
    def search_hashtag(self, hashtag, max_users=100):
        """해시태그 검색 및 유저네임 수집"""
        if hashtag not in self.collected_data["hashtags"]:
            self.collected_data["hashtags"][hashtag] = {
                "usernames": [],
                "last_updated": "",
                "total_collected": 0
            }
        
        existing_usernames = set(self.collected_data["hashtags"][hashtag]["usernames"])
        print(f"\n이전에 수집된 유저네임 수: {len(existing_usernames)}")
        
        try:
            self.driver.get(f"https://www.tiktok.com/tag/{hashtag}")
            time.sleep(5)
            
            input("캡챠나 팝업이 있다면 해결 후 Enter 키를 눌러주세요...")
            
            new_usernames = set()
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 20
            
            while scroll_attempts < max_scroll_attempts:
                try:
                    video_containers = self.wait.until(EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "div[data-e2e='challenge-item-list'] > div")))
                    
                    for container in video_containers:
                        try:
                            author_element = container.find_element(By.CSS_SELECTOR, "a[href*='/@']")
                            username = author_element.get_attribute("href").split("/@")[-1].split("?")[0]
                            
                            if username and username not in existing_usernames:
                                new_usernames.add(username)
                                print(f"새로 수집된 유저네임: {username}")
                                
                                try:
                                    video_desc = container.find_element(By.CSS_SELECTOR, "[data-e2e='challenge-item-desc']").text
                                    print(f"비디오 설명: {video_desc}")
                                except:
                                    pass
                                
                        except Exception as e:
                            continue
                    
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(4)
                    
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        scroll_attempts += 1
                        print(f"스크롤 시도 {scroll_attempts}/{max_scroll_attempts}")
                    else:
                        scroll_attempts = 0
                        last_height = new_height
                    
                    if len(new_usernames) + len(existing_usernames) >= max_users:
                        print(f"목표 유저네임 수 달성 (기존: {len(existing_usernames)}, 신규: {len(new_usernames)})")
                        break
                        
                except Exception as e:
                    print(f"데이터 수집 중 오류 발생: {str(e)}")
                    scroll_attempts += 1
                    time.sleep(2)
                    continue
            
            # 새로운 유저네임 추가 및 저장
            all_usernames = list(existing_usernames | new_usernames)
            self.collected_data["hashtags"][hashtag] = {
                "usernames": all_usernames,
                "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_collected": len(all_usernames)
            }
            self.save_collected_data()
            
            return list(new_usernames)
            
        except Exception as e:
            print(f"검색 중 오류 발생: {str(e)}")
            return []
        
    def save_usernames(self, new_usernames, hashtag):
        """새로 수집된 유저네임 저장"""
        if not new_usernames:
            print("새로 수집된 유저네임이 없습니다.")
            return
            
        filename = f"new_usernames_{hashtag}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "hashtag": hashtag,
                "new_users": len(new_usernames),
                "total_users": len(self.collected_data["hashtags"][hashtag]["usernames"]),
                "new_usernames": new_usernames,
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
            }, f, ensure_ascii=False, indent=2)
        print(f"새로운 유저네임이 {filename}에 저장되었습니다.")
    
    def close(self):
        """드라이버 종료"""
        self.driver.quit()

def main():
    scraper = TikTokHashtagScraper()
    try:
        while True:
            print("\n1. 단일 해시태그 검색")
            print("2. 여러 해시태그 검색")
            print("3. 수집된 데이터 통계")
            print("4. 종료")
            
            choice = input("\n선택하세요 (1-4): ")
            
            if choice == "1":
                hashtag = input("검색할 해시태그를 입력하세요 (#제외): ")
                max_users = int(input("수집할 최대 유저 수를 입력하세요 (기본: 100): ") or 100)
                print(f"\n'{hashtag}' 해시태그 검색 시작...")
                new_usernames = scraper.search_hashtag(hashtag, max_users)
                scraper.save_usernames(new_usernames, hashtag)
                
            elif choice == "2":
                hashtags = input("검색할 해시태그들을 쉼표로 구분하여 입력하세요: ").split(",")
                max_users = int(input("해시태그당 수집할 최대 유저 수를 입력하세요 (기본: 100): ") or 100)
                
                for hashtag in hashtags:
                    hashtag = hashtag.strip()
                    print(f"\n'{hashtag}' 해시태그 검색 시작...")
                    new_usernames = scraper.search_hashtag(hashtag, max_users)
                    scraper.save_usernames(new_usernames, hashtag)
                    
            elif choice == "3":
                print("\n수집된 데이터 통계:")
                for hashtag, data in scraper.collected_data["hashtags"].items():
                    print(f"\n해시태그: {hashtag}")
                    print(f"총 수집된 유저 수: {data['total_collected']}")
                    print(f"마지막 업데이트: {data['last_updated']}")
                    
            elif choice == "4":
                print("\n프로그램을 종료합니다.")
                break
                
    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"\n예상치 못한 오류 발생: {str(e)}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
