import os
import re
import sys
import time
from time import sleep

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# 경력 및 필터 조건이 적용된 채용 공고 url
FILTERED_RECRUITMENT_URL = 'https://www.wanted.co.kr/wdlist/518?country=kr&job_sort=job.popularity_order&years=5&selected=872&selected=660&locations=seoul.all&locations=incheon.all&locations=gyeonggi.all'

# 채용 공고 포지션에 이 정규식과 매칭되는 공고는 필터링한다.
FILTERING_POSITION_REGEX = '(front|프론트|Node\\.?js|Python|신입|안드로이드|android|php|jsp)'

# 채용 공고 회사에 이 정규식과 매칭되는 공고는 필터링한다.
FILTERING_COMPANY_REGEX = '(우아한형제들|프리윌린)'

# 필터링 되어야하는 회사들의 태그
FILTERING_TAGS = ['50명이하']

# JD에 있어야할 단어들에 대한 정규식
JOB_DESCRIPTION_REGEXES = ['(java|자바|kotlin|코틀린)', '(spring|스프링)']

already_added = list()
now_added = list()


def run():
    email = sys.argv[1]
    password = sys.argv[2]

    options = Options()
    options.add_argument('--start-fullscreen')

    driver = get_chrome_driver(options)

    base_url = 'https://www.wanted.co.kr'
    driver.get(url=base_url)

    login(driver, email, password)

    sleep(2)

    driver.get(url=FILTERED_RECRUITMENT_URL)

    sleep(2)

    scroll_down_to_the_end(driver)

    hrefs = get_recruitment_hrefs(driver)
    hrefs_length = len(hrefs)

    print('1차 필터링 된 채용 공고 수 : ' + str(hrefs_length))

    start = time.time()
    print('채용 공고 상세 페이지 조회 시작')
    last_progress = 0

    index = 0
    err_index = 0
    retry_count = 0

    while index < hrefs_length:
        href = hrefs[index]

        try:
            add_bookmark(driver, href)
        except Exception as e:
            if err_index != index:
                retry_count = 1
                err_index = index
            else:
                retry_count += 1

            print('에러 발생. href : ' + href)

        now_progress = int((index + 1) * 100 / hrefs_length)

        index += 1
        if now_progress != last_progress:
            print_status(now_progress)
            last_progress = now_progress

    end = time.time()
    print('채용 공고 상세 페이지 조회 끝. 소요 시간 : ' + get_elapsed_time_str(end - start))

    print()
    print('* 이미 북마크 되어 있던 채용 공고 수 : ' + str(len(already_added)))
    if already_added:
        print('[이미 북마크 되어 있던 채용 공고 목록]')
        print(*already_added, sep='\n')

    print()
    print('* 북마크된 채용 공고 수 : ' + str(len(now_added)))
    if now_added:
        print('[북마크된 채용 공고 목록]')
        print(*now_added, sep='\n')


def get_chrome_driver(options):
    driver = webdriver.Chrome(options=options, service=Service(ChromeDriverManager().install()))
    driver.implicitly_wait(time_to_wait=10)
    return driver


def login(driver, email, password):
    login_button = driver.find_element(by=By.CLASS_NAME, value='Button_Button__interaction__kkYaa')
    login_button.click()

    email_login_button = driver.find_element(by=By.CLASS_NAME, value='css-1d79him')
    email_login_button.click()

    email_input = driver.find_element(by=By.NAME, value='email')
    email_input.send_keys(email)

    password_input = driver.find_element(by=By.NAME, value='password')
    password_input.send_keys(password)

    enter_password_button = driver.find_element(by=By.CLASS_NAME, value='css-1yzn4b')
    enter_password_button.click()


# 스크롤 다운 후 데이터가 로드되기까지 기다리는 최대 시간. 인터넷 환경이 안 좋은 곳에 경우 이 값을 더 늘릴 필요가 있다.
# 이 값을 늘린다고 해서 스크롤 속도가 느려지진 않는다. 다만 맨 마지막 스크롤이 끝난 후에 대기하는 시간이 좀 길어질 것이다.
MAX_WAIT_SECONDS = 20


def scroll_down_to_the_end(driver):
    start = time.time()
    print('스크롤 다운을 통한 데이터 탐색 시작')

    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # 끝까지 스크롤 다운
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # 스크롤 다운 후 스크롤 높이 다시 가져옴
        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            wait_seconds = 0

            while wait_seconds < MAX_WAIT_SECONDS:
                # 1초 대기
                sleep(1)
                wait_seconds += 1
                new_height = driver.execute_script("return document.body.scrollHeight")

                if new_height != last_height:
                    break

            if wait_seconds >= MAX_WAIT_SECONDS:
                break

        last_height = new_height

    end = time.time()
    print('스크롤 다운을 통한 데이터 탐색 끝. 소요 시간 : ' + get_elapsed_time_str(end - start))


def get_recruitment_hrefs(driver):
    start = time.time()
    print('채용 공고 URL 추출 시작')

    li_tags = driver.find_elements(by=By.CLASS_NAME, value='Card_Card__lU7z_')
    while li_tags is None:
        li_tags = driver.find_elements(by=By.XPATH, value='Card_Card__lU7z_')

    filtered_li_tags = list(filter(
        lambda li: not re.search(FILTERING_POSITION_REGEX, get_job_position(li), re.IGNORECASE) and not re.search(
            FILTERING_COMPANY_REGEX, get_company_name(li), re.IGNORECASE), li_tags))
    hrefs = list(map(lambda li: get_a_tag_href(li), filtered_li_tags))

    # 기존에 한 번 사용했던 url은 제외시킨다.
    filtering_href_file_path = os.getcwd() + '/filtering-hrefs.txt'

    if os.path.isfile(filtering_href_file_path):
        filtering_hrefs = open(filtering_href_file_path, 'r').read().strip().split(',\n')
        hrefs = list(filter(lambda href: href not in filtering_hrefs, hrefs))

    # 조회된 url append
    if os.path.isfile(filtering_href_file_path):
        hrefs_file = open(filtering_href_file_path, 'a')
        hrefs_file.write(',\n' + ',\n'.join(hrefs))
    else:
        hrefs_file = open(filtering_href_file_path, 'w')
        hrefs_file.write(',\n'.join(hrefs))

    hrefs.reverse()

    end = time.time()
    print('채용 공고 URL 추출 끝. 소요 시간 : ' + get_elapsed_time_str(end - start))
    return hrefs


def get_job_position(data):
    position = data.find_element(by=By.CLASS_NAME, value='JobCard_JobCard__body__position__P8R0W')
    while position is None:
        position = data.find_element(by=By.CLASS_NAME, value='JobCard_JobCard__body__position__P8R0W')

    return position.text


def get_company_name(data):
    company_name = data.find_element(by=By.CLASS_NAME, value='JobCard_JobCard__body__company__F6XoH')
    while company_name is None:
        company_name = data.find_element(by=By.CLASS_NAME, value='JobCard_JobCard__body__company__F6XoH')

    return company_name.text


def get_a_tag_href(data):
    a_tag = data.find_element(by=By.TAG_NAME, value='a')
    while a_tag is None:
        a_tag = data.find_element(by=By.TAG_NAME, value='a')

    return a_tag.get_attribute('href')


def add_bookmark(driver, href):
    driver.get(href)
    job_description = get_job_description(driver)
    tag_texts = driver.find_element(by=By.CLASS_NAME, value='CompanyTags_CompanyTags__list__KgTBZ').text

    if is_fit_jd(job_description) and is_fit_tags(tag_texts):
        bookmark_button = get_bookmark_button(driver)

        if bookmark_button is not None:
            company = driver.find_elements(by=By.CLASS_NAME, value='JobHeader_JobHeader__Tools__Company__Link__QjFBa')[0].text
            position = driver.find_element(by=By.TAG_NAME, value='h1').text

            addable = bookmark_button.get_attribute('data-kind') == 'add'

            if addable:
                bookmark_button.send_keys(Keys.ENTER)
                now_added.append(company + ' : ' + position)
            else:
                already_added.append(company + ' : ' + position)


def get_job_description(driver):
    detail_button = driver.find_element(by=By.CLASS_NAME, value='Button_Button__fullWidth__RU4tf')
    detail_button.send_keys(Keys.ENTER)

    job_description = driver.find_element(by=By.CLASS_NAME, value='JobDescription_JobDescription__VWfcb')
    while job_description is None or job_description == '':
        job_description = driver.find_element(by=By.CLASS_NAME, value='JobDescription_JobDescription__VWfcb')

    return job_description.text


def is_fit_jd(job_description):
    result = True

    for regex in JOB_DESCRIPTION_REGEXES:
        match = re.search(regex, job_description, re.IGNORECASE)
        if not match:
            result = False
            break

    return result


def is_fit_tags(tag_texts):
    result = True

    for filtering_tag in FILTERING_TAGS:
        if filtering_tag in tag_texts:
            result = False
            break

    return result


def get_bookmark_button(driver):
    bookmark_buttons = driver.find_elements(by=By.CLASS_NAME, value='BookmarkBtn_BookmarkBtn__head__MbDMM')

    i = 0
    while not bookmark_buttons and i < 3:
        bookmark_buttons = driver.find_elements(by=By.CLASS_NAME, value='BookmarkBtn_BookmarkBtn__head__MbDMM')
        i += 1

    if bookmark_buttons:
        return bookmark_buttons[0]
    else:
        return None


def print_status(now_progress):
    print('진행도 : ' + '{:>3}'.format(str(now_progress)) + '% [' + '#' * now_progress + ' ' * (100 - now_progress) + ']')


def get_elapsed_time_str(elapsed_total_seconds):
    elapsed_minutes = int(elapsed_total_seconds / 60)
    elapsed_seconds = int(elapsed_total_seconds % 60)
    return str(elapsed_minutes) + '분 ' + str(elapsed_seconds) + '초'


if __name__ == "__main__":
    run()
