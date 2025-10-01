#!/usr/bin/env python3
"""
TikTok 쿠키 추출 스크립트
수동 로그인 후 쿠키를 자동으로 JSON 파일로 저장
"""

import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def extract_tiktok_cookies(output_file="tiktok-hashtag-scraper/cookies.json"):
    """TikTok 쿠키 추출"""
    print("🍪 TikTok 쿠키 추출 도구")
    print("=" * 50)

    # Chrome 옵션 설정
    options = Options()
    # 브라우저를 표시 (헤드리스 모드 비활성화)
    # options.add_argument("--headless")  # 주석 처리하여 브라우저 표시

    # 드라이버 초기화
    print("🌐 Chrome 브라우저 시작 중...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        # TikTok 접속
        print("📱 TikTok 웹사이트 접속 중...")
        driver.get("https://www.tiktok.com")

        print("\n" + "=" * 50)
        print("⚠️  지금 브라우저에서 TikTok에 로그인하세요!")
        print("=" * 50)
        print("\n다음 방법 중 하나로 로그인:")
        print("1. 이메일/전화번호")
        print("2. 소셜 계정 (Google, Facebook 등)")
        print("\n로그인이 완료되면 아래 Enter를 누르세요...\n")

        input()

        # 쿠키 추출
        print("\n🍪 쿠키 추출 중...")
        cookies = driver.get_cookies()

        # JSON 형식으로 변환
        cookies_json = []
        for cookie in cookies:
            cookies_json.append({
                "name": cookie.get("name"),
                "value": cookie.get("value"),
                "domain": cookie.get("domain")
            })

        # 파일로 저장
        with open(output_file, 'w') as f:
            json.dump(cookies_json, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 쿠키가 성공적으로 저장되었습니다!")
        print(f"📁 파일 위치: {output_file}")
        print(f"🍪 추출된 쿠키 수: {len(cookies_json)}개")

        # 중요한 쿠키 확인
        important_cookies = ['sessionid', 'sid_tt', 'uid_tt', 'msToken', 'ttwid']
        found_cookies = [c['name'] for c in cookies_json if c['name'] in important_cookies]

        print(f"\n📋 중요 쿠키 확인:")
        for cookie_name in important_cookies:
            if cookie_name in found_cookies:
                print(f"  ✅ {cookie_name}")
            else:
                print(f"  ❌ {cookie_name} (누락)")

        if len(found_cookies) < 3:
            print("\n⚠️  경고: 로그인이 제대로 되지 않았을 수 있습니다.")
            print("   브라우저에서 TikTok에 로그인했는지 확인하세요.")
        else:
            print("\n🎉 쿠키 추출 완료! 스크래퍼를 실행할 수 있습니다.")

    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
    finally:
        print("\n🔒 브라우저 종료 중...")
        driver.quit()
        print("✅ 완료!")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TikTok 쿠키 추출 도구")
    parser.add_argument(
        "--output", "-o",
        default="tiktok-hashtag-scraper/cookies.json",
        help="쿠키를 저장할 파일 경로 (기본: tiktok-hashtag-scraper/cookies.json)"
    )

    args = parser.parse_args()

    extract_tiktok_cookies(args.output)
