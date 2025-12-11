// TikTok 쿠키 추출 코드
(async function() {
    try {
        // 모든 쿠키 가져오기
        const cookies = await cookieStore.getAll();
        
        // 필요한 형식으로 변환
        const formattedCookies = cookies.map(cookie => ({
            name: cookie.name,
            value: cookie.value,
            domain: cookie.domain || '.tiktok.com',
            path: cookie.path || '/',
            secure: cookie.secure || true,
            httpOnly: cookie.httpOnly || false
        }));
        
        // JSON 문자열로 변환
        const jsonString = JSON.stringify(formattedCookies, null, 2);
        
        // 클립보드에 복사
        await navigator.clipboard.writeText(jsonString);
        
        console.log('✅ 쿠키가 클립보드에 복사되었습니다!');
        console.log(`📊 총 ${formattedCookies.length}개의 쿠키를 추출했습니다.`);
        console.log('\n미리보기:');
        console.log(jsonString.substring(0, 500) + '...');
        
        // 다운로드도 제공
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'cookies.json';
        a.click();
        URL.revokeObjectURL(url);
        
        console.log('💾 cookies.json 파일도 다운로드되었습니다!');
        
    } catch (error) {
        console.error('❌ 오류 발생:', error);
        console.log('\n🔄 구버전 브라우저용 대체 코드 실행 중...');
        
        // 구버전 브라우저 대체 코드
        const cookieString = document.cookie;
        const cookieArray = cookieString.split('; ').map(cookie => {
            const [name, value] = cookie.split('=');
            return {
                name: name,
                value: value,
                domain: '.tiktok.com',
                path: '/',
                secure: true,
                httpOnly: false
            };
        });
        
        const jsonString = JSON.stringify(cookieArray, null, 2);
        console.log(jsonString);
        console.log('\n⚠️ 위 내용을 복사하여 cookies.json 파일로 저장하세요.');
    }
})();