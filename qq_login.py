# Generated by Selenium IDE
import subprocess
from collections import Counter
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from config import *
from log import logger, color
from update import get_netdisk_addr
from version import now_version


class LoginResult(ConfigInterface):
    def __init__(self, uin="", skey="", openid="", p_skey="", vuserid="", qc_openid="", qc_k=""):
        super().__init__()
        # 使用炎炎夏日活动界面得到
        self.uin = uin
        self.skey = skey
        # 登录QQ空间得到
        self.p_skey = p_skey
        # 使用心悦活动界面得到
        self.openid = openid
        # 使用腾讯视频相关页面得到
        self.vuserid = vuserid
        # 登录电脑管家页面得到
        self.qc_openid = qc_openid
        self.qc_k = qc_k


class QQLogin():
    login_type_auto_login = "账密自动登录"
    login_type_qr_login = "扫码登录"

    login_mode_normal = "normal"
    login_mode_xinyue = "xinyue"
    login_mode_qzone = "qzone"
    login_mode_guanjia = "guanjia"
    login_mode_wegame = "wegame"

    bandizip_executable_path = os.path.realpath("./bandizip_portable/bz.exe")
    chrome_driver_executable_path = os.path.realpath("./chromedriver_87.exe")
    chrome_binary_7z = os.path.realpath("./chrome_portable_87.7z")
    chrome_binary_directory = os.path.realpath("./chrome_portable_87")
    chrome_binary_location = os.path.realpath("./chrome_portable_87/chrome.exe")

    default_window_width = 390
    default_window_height = 360

    def __init__(self, common_config):
        self.cfg = common_config  # type: CommonConfig
        self.driver = None  # type: WebDriver
        self.window_title = ""
        self.time_start_login = datetime.datetime.now()

    def prepare_chrome(self, ctx, login_type, login_url):
        logger.info(color("fg_bold_cyan") + f"正在初始化chrome driver，用以进行【{ctx}】相关操作")
        caps = DesiredCapabilities().CHROME
        # caps["pageLoadStrategy"] = "normal"  #  Waits for full page load
        caps["pageLoadStrategy"] = "none"  # Do not wait for full page load

        options = Options()
        options.add_argument(f"window-size={self.default_window_width},{self.default_window_height}")
        options.add_argument(f"app={login_url}")
        if not self.cfg._debug_show_chrome_logs:
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
        if self.cfg.run_in_headless_mode:
            if login_type == self.login_type_auto_login:
                logger.warning("已配置在自动登录模式时使用headless模式运行chrome")
                options.headless = True
            else:
                logger.warning("扫码登录模式不使用headless模式")

        inited = False

        try:
            if not self.cfg.force_use_portable_chrome:
                # 如果未强制使用便携版chrome，则首先尝试使用系统安装的chrome
                self.driver = webdriver.Chrome(executable_path=self.chrome_driver_executable_path, desired_capabilities=caps, options=options)
                logger.info("使用自带chrome")
                inited = True
        except:
            pass

        if not inited:
            # 如果找不到，则尝试使用打包的便携版chrome
            # 先判定本地是否有便携版压缩包，若无则提示去网盘下载
            if not os.path.isfile(self.chrome_binary_7z):
                msg = (
                    "================ 这一段是问题描述 ================\n"
                    "当前电脑未发现合适版本chrome浏览器版本，且当前目录无便携版chrome浏览器的压缩包({zip_name})\n"
                    "\n"
                    "================ 这一段是解决方法 ================\n"
                    "如果不想影响系统浏览器，请在稍后打开的网盘页面中下载[{zip_name}]，并放到小助手的exe所在目录（注意：是把这个压缩包原原本本地放到这个目录里，而不是解压后再放过来！！！），然后重新打开程序~\n"
                    "如果愿意装一个浏览器，请在稍后打开的网盘页面中下载Chrome_87.0.4280.141_普通安装包_非便携版.exe，下载完成后双击安装即可\n"
                    "\n"
                    "================ 这一段是补充说明 ================\n"
                    "如果之前版本已经下载过这个文件，可以直接去之前版本复制过来~不需要再下载一次~\n"
                    "\n"
                    "------- 如果这样还有人进群问，将直接踢出群聊 -------\n"
                ).format(zip_name=os.path.basename(self.chrome_binary_7z))
                win32api.MessageBox(0, msg, "你没有chrome浏览器，需要安装完整版或下载便携版", win32con.MB_ICONERROR)
                webbrowser.open(get_netdisk_addr(self.cfg))
                os.system("PAUSE")
                exit(-1)

            # 先判断便携版chrome是否已解压
            if not os.path.isdir(self.chrome_binary_directory):
                logger.info("自动解压便携版chrome到当前目录")
                subprocess.call([self.bandizip_executable_path, "x", "-target:auto", self.chrome_binary_7z])

            # 然后使用本地的chrome来初始化driver对象
            options.binary_location = self.chrome_binary_location
            # you may need some other options
            options.add_argument('--no-sandbox')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--no-first-run')
            self.driver = webdriver.Chrome(executable_path=self.chrome_driver_executable_path, desired_capabilities=caps, options=options)
            logger.info("使用便携版chrome")

        self.cookies = self.driver.get_cookies()

    def destroy_chrome(self):
        if self.driver is not None:
            # 最小化网页
            self.driver.minimize_window()
            threading.Thread(target=self.driver.quit, daemon=True).start()

    def login(self, account, password, login_mode="normal", name=""):
        """
        自动登录指定账号，并返回登陆后的cookie中包含的uin、skey数据
        :param account: 账号
        :param password: 密码
        :rtype: LoginResult
        """
        self.window_title = f"将登录 {name}({account}) - {login_mode}"
        logger.info("即将开始自动登录，无需任何手动操作，等待其完成即可")
        logger.info("如果出现报错，可以尝试调高相关超时时间然后重新执行脚本")

        def login_with_account_and_password():
            logger.info(color("bold_green") + "当前为自动登录模式，请不要手动操作网页，否则可能会导致登录流程失败")

            # 切换到自动登录界面
            logger.info("等待#switcher_plogin加载完毕")
            time.sleep(self.cfg.login.open_url_wait_time)
            WebDriverWait(self.driver, self.cfg.login.load_login_iframe_timeout).until(expected_conditions.visibility_of_element_located((By.ID, 'switcher_plogin')))

            # 选择密码登录
            self.driver.find_element(By.ID, "switcher_plogin").click()

            # 输入账号
            self.driver.find_element(By.ID, "u").send_keys(account)
            # 输入密码
            self.driver.find_element(By.ID, "p").send_keys(password)

            logger.info("等待一会，确保登录键可以点击")
            time.sleep(3)

            # 发送登录请求
            self.driver.find_element(By.ID, "login_button").click()

            # 尝试自动处理验证码
            self.try_auto_resolve_captcha()

        return self._login(self.login_type_auto_login, login_action_fn=login_with_account_and_password, login_mode=login_mode)

    def qr_login(self, login_mode="normal", name=""):
        """
        二维码登录，并返回登陆后的cookie中包含的uin、skey数据
        :rtype: LoginResult
        """
        logger.info("即将开始扫码登录，请在弹出的网页中扫码登录~")
        self.window_title = f"请扫码 {name} - {login_mode}"

        def login_with_qr_code():
            logger.info(color("bold_yellow") + f"请在{self.cfg.login.login_timeout}s内完成扫码登录操作或快捷登录操作")

        return self._login(self.login_type_qr_login, login_action_fn=login_with_qr_code, login_mode=login_mode)

    def _login(self, login_type, login_action_fn=None, login_mode="normal"):
        for idx in range(self.cfg.login.max_retry_count):
            idx += 1

            self.login_mode = login_mode

            # note: 如果get_login_url的surl变更，代码中确认登录完成的地方也要一起改
            login_fn, suffix, login_url = {
                self.login_mode_normal: (
                    self._login_real,
                    "",
                    self.get_login_url(21000127, 8, "https://dnf.qq.com/"),
                ),
                self.login_mode_xinyue: (
                    self._login_xinyue_real,
                    "心悦",
                    "https://xinyue.qq.com/act/a20181101rights/index.html",
                ),
                self.login_mode_qzone: (
                    self._login_qzone,
                    "QQ空间业务（如抽卡等需要用到）（不启用QQ空间系活动就不会触发本类型的登录，完整列表参见示例配置）",
                    self.get_login_url(15000103, 5, "https://act.qzone.qq.com/"),
                ),
                self.login_mode_guanjia: (
                    self._login_guanjia,
                    "电脑管家（如电脑管家蚊子腿需要用到，完整列表参见示例配置）",
                    "http://guanjia.qq.com/act/cop/20210127dnf/pc/",
                ),
                self.login_mode_wegame: (
                    self._login_wegame,
                    "wegame（获取wegame相关api需要用到）",
                    self.get_login_url(1600001063, 733, "https://www.wegame.com.cn/"),
                ),
            }[login_mode]

            ctx = f"{login_type}-{suffix}"

            try:
                self.prepare_chrome(ctx, login_type, login_url)

                return login_fn(ctx, login_action_fn=login_action_fn)
            except Exception as e:
                logger.exception(f"第{idx}/{self.cfg.login.max_retry_count}次尝试登录出错，等待{self.cfg.login.retry_wait_time}秒后重试", exc_info=e)
                time.sleep(self.cfg.login.retry_wait_time)
            finally:
                used_time = datetime.datetime.now() - self.time_start_login
                logger.info("")
                logger.info(color("bold_yellow") + f"本次 {ctx} 共耗时为 {used_time}")
                logger.info("")
                self.destroy_chrome()

        # 能走到这里说明登录失败了，大概率是网络不行
        logger.warning(color("bold_yellow") + (
            f"已经尝试登录{self.cfg.login.max_retry_count}次，均已失败，大概率是网络有问题\n"
            "建议依次尝试下列措施\n"
            "1. 重新打开程序\n"
            "2. 重启电脑\n"
            "3. 更换dns，如谷歌、阿里、腾讯、百度的dns，具体更换方法请百度\n"
            "4. 重装网卡驱动\n"
            "5. 换个网络环境\n"
            "6. 换台电脑\n"
        ))
        raise Exception("网络有问题")

    def _login_real(self, login_type, login_action_fn=None):
        """
        通用登录逻辑，并返回登陆后的cookie中包含的uin、skey数据
        :rtype: LoginResult
        """
        s_url = "https://dnf.qq.com/"

        def switch_to_login_frame_fn():
            # self.get_switch_to_login_frame_fn(21000127, 8, s_url)
            pass

        def assert_login_finished_fn():
            logger.info("请等待网页切换为目标网页，则说明已经登录完成了...")
            WebDriverWait(self.driver, self.cfg.login.login_finished_timeout).until(expected_conditions.url_to_be(s_url))

        self._login_common(login_type, switch_to_login_frame_fn, assert_login_finished_fn, login_action_fn)

        # 从cookie中获取uin和skey
        return LoginResult(uin=self.get_cookie("uin"), skey=self.get_cookie("skey"),
                           p_skey=self.get_cookie("p_skey"), vuserid=self.get_cookie("vuserid"))

    def _login_qzone(self, login_type, login_action_fn=None):
        """
        通用登录逻辑，并返回登陆后的cookie中包含的uin、skey数据
        :rtype: LoginResult
        """
        s_url = "https://act.qzone.qq.com/"

        def switch_to_login_frame_fn():
            # self.get_switch_to_login_frame_fn(15000103, 5, s_url)
            pass

        def assert_login_finished_fn():
            logger.info("请等待网页切换为目标网页，则说明已经登录完成了...")
            WebDriverWait(self.driver, self.cfg.login.login_finished_timeout).until(expected_conditions.url_to_be(s_url))

        self._login_common(login_type, switch_to_login_frame_fn, assert_login_finished_fn, login_action_fn)

        # 从cookie中获取uin和skey
        return LoginResult(p_skey=self.get_cookie("p_skey"),
                           uin=self.get_cookie("uin"), skey=self.get_cookie("skey"), vuserid=self.get_cookie("vuserid"))

    def _login_guanjia(self, login_type, login_action_fn=None):
        """
        通用登录逻辑，并返回登陆后的cookie中包含的uin、skey数据
        :rtype: LoginResult
        """

        def switch_to_login_frame_fn():
            logger.info("打开活动界面")
            # self.open_url_on_start("http://guanjia.qq.com/act/cop/20210127dnf/pc/")
            pass

            self.set_window_size()

            logger.info("等待登录按钮#dologin出来，确保加载完成")
            WebDriverWait(self.driver, self.cfg.login.load_page_timeout).until(expected_conditions.visibility_of_element_located((By.ID, "dologin")))

            logger.info("点击登录按钮")
            self.driver.find_element(By.ID, "dologin").click()

            logger.info("等待#login_ifr显示出来并切换")
            WebDriverWait(self.driver, self.cfg.login.load_login_iframe_timeout).until(expected_conditions.visibility_of_element_located((By.ID, "login_ifr")))
            loginIframe = self.driver.find_element_by_id("login_ifr")
            self.driver.switch_to.frame(loginIframe)

            logger.info("等待#login_ifr#ptlogin_iframe加载完毕并切换")
            WebDriverWait(self.driver, self.cfg.login.load_login_iframe_timeout).until(expected_conditions.visibility_of_element_located((By.ID, "ptlogin_iframe")))
            ptlogin_iframe = self.driver.find_element_by_id("ptlogin_iframe")
            self.driver.switch_to.frame(ptlogin_iframe)

        def assert_login_finished_fn():
            logger.info("请等待#logined的div可见，则说明已经登录完成了...")
            WebDriverWait(self.driver, self.cfg.login.login_finished_timeout).until(expected_conditions.visibility_of_element_located((By.ID, "logined")))

        self._login_common(login_type, switch_to_login_frame_fn, assert_login_finished_fn, login_action_fn)

        # 从cookie中获取uin和skey
        return LoginResult(qc_openid=self.get_cookie("__qc__openid"), qc_k=self.get_cookie("__qc__k"),
                           uin=self.get_cookie("uin"), skey=self.get_cookie("skey"), p_skey=self.get_cookie("p_skey"), vuserid=self.get_cookie("vuserid"))

    def _login_wegame(self, login_type, login_action_fn=None):
        """
        通用登录逻辑，并返回登陆后的cookie中包含的uin、skey数据
        :rtype: LoginResult
        """
        s_url = "https://www.wegame.com.cn/"

        def switch_to_login_frame_fn():
            # self.get_switch_to_login_frame_fn(1600001063, 733, s_url)
            pass

        def assert_login_finished_fn():
            logger.info("请等待网页切换为目标网页，则说明已经登录完成了...")
            WebDriverWait(self.driver, self.cfg.login.login_finished_timeout).until(expected_conditions.url_to_be(s_url))

        self._login_common(login_type, switch_to_login_frame_fn, assert_login_finished_fn, login_action_fn)

        # 从cookie中获取uin和skey
        return LoginResult(uin=self.get_cookie("uin"), skey=self.get_cookie("skey"), p_skey=self.get_cookie("p_skey"))

    def _login_xinyue_real(self, login_type, login_action_fn=None):
        """
        通用登录逻辑，并返回登陆后的cookie中包含的uin、skey数据
        :rtype: LoginResult
        """

        def switch_to_login_frame_fn():
            logger.info("打开活动界面")
            # self.open_url_on_start("https://xinyue.qq.com/act/a20181101rights/index.html")
            pass

            self.set_window_size()

            logger.info("等待#loginframe加载完毕并切换")
            WebDriverWait(self.driver, self.cfg.login.load_login_iframe_timeout).until(expected_conditions.visibility_of_element_located((By.CLASS_NAME, "loginframe")))
            login_frame = self.driver.find_element_by_class_name("loginframe")
            self.driver.switch_to.frame(login_frame)

            logger.info("等待#loginframe#ptlogin_iframe加载完毕并切换")
            WebDriverWait(self.driver, self.cfg.login.load_login_iframe_timeout).until(expected_conditions.visibility_of_element_located((By.ID, "ptlogin_iframe")))
            ptlogin_iframe = self.driver.find_element_by_id("ptlogin_iframe")
            self.driver.switch_to.frame(ptlogin_iframe)

        def assert_login_finished_fn():
            logger.info("请等待#btn_wxqclogin可见，则说明已经登录完成了...")
            WebDriverWait(self.driver, self.cfg.login.login_finished_timeout).until(expected_conditions.invisibility_of_element_located((By.ID, "btn_wxqclogin")))

            logger.info("等待1s，确认获取openid的请求完成")
            time.sleep(1)

            # 确保openid已设置
            for t in range(1, 3 + 1):
                if self.driver.get_cookie('openid') is None:
                    logger.info(f"第{t}/3未在心悦的cookie中找到openid，等一秒再试")
                    time.sleep(1)
                    continue
                break

        self._login_common(login_type, switch_to_login_frame_fn, assert_login_finished_fn, login_action_fn)

        # 从cookie中获取openid
        return LoginResult(openid=self.get_cookie("openid"))

    def get_switch_to_login_frame_fn(self, appid, daid, s_url, style=34, theme=2):
        # 参数：appid  daid
        # 21000127      8       普通游戏活动        https://dnf.qq.com/
        # 15000103      5       qq空间             https://act.qzone.qq.com/
        # 716027609     383     安全管家            https://guanjia.qq.com/
        # 1600001063    733     wegame             https://www.wegame.com.cn/
        # 716027609     383     心悦战场            https://xinyue.qq.com/
        # 21000115      8       腾讯游戏/移动游戏    https://dnf.qq.com/
        # 532001604     ?       腾讯视频            https://film.qq.com/

        # 参数：s_url
        # 登陆完毕后要跳转的网页

        # 参数：style
        # 仅二维码 样式一（QQ邮箱设备锁）：30
        # 二维码/快捷/密码 样式一（整个页面-与之前的兼容（其实就是原来点登录的弹窗））：0/11-15/17/19-23/32-33/40
        # 二维码/快捷/密码 样式二（限定大小）：25
        # 二维码/快捷/密码 样式三（限定大小-格式美化）：34 re: 选用
        # 二维码/快捷/密码 样式四（居中-移动端风格-需要在手机上，且安装手机QQ后才可以）：35/42

        # 参数：theme
        # 绿色风格：1
        # 蓝色风格：2 re: 选用
        logger.info("打开登录界面")
        login_url = self.get_login_url(appid, daid, s_url, style, theme)
        self.open_url_on_start(login_url)

    def get_login_url(self, appid, daid, s_url, style=34, theme=2):
        return f"https://xui.ptlogin2.qq.com/cgi-bin/xlogin?appid={appid}&daid={daid}&s_url={quote_plus(s_url)}&style={style}&theme={theme}&target=self"

    def _login_common(self, login_type, switch_to_login_frame_fn, assert_login_finished_fn, login_action_fn=None):
        """
        通用登录逻辑，并返回登陆后的cookie中包含的uin、skey数据
        :rtype: LoginResult
        """
        switch_to_login_frame_fn()

        self.driver.execute_script(f"document.title = '{self.window_title}'")

        # 实际登录的逻辑，不同方式的处理不同，这里调用外部传入的函数
        logger.info(f"开始{login_type}流程")
        if login_action_fn is not None:
            login_action_fn()

        logger.info("等待登录完成（也就是#loginIframe#login登录框消失）")
        # 出验证码的时候，下面这个操作可能会报错 'target frame detached\n(Session info: chrome=87.0.4280.88)'
        # 这时候等待一下好像就行了
        for i in range(3):
            try:
                WebDriverWait(self.driver, self.cfg.login.login_timeout).until(expected_conditions.invisibility_of_element_located((By.ID, "login")))
                break
            except Exception as e:
                logger.error("出错了，等待两秒再重试", exc_info=e)
                time.sleep(2)

        logger.info("回到主iframe")
        self.driver.switch_to.default_content()

        assert_login_finished_fn()

        logger.info("登录完成")

        self.cookies = self.driver.get_cookies()

        if self.login_mode == self.login_mode_normal:
            # 普通登录额外获取腾讯视频的vqq_vuserid
            self.fetch_qq_video_vuserid()
        elif self.login_mode == self.login_mode_qzone:
            self.fetch_qq_video_vuserid()
            # logger.info("QQ空间登录类型额外访问一下征集令活动界面，然后还得刷新一遍浏览器，不然不刷新次数（什么鬼）")
            # logger.info("第一次访问，并停留5秒")
            # self.driver.get("https://act.qzone.qq.com/vip/2020/dnf1126")
            # time.sleep(5)
            # logger.info("第二次访问，并停留5秒")
            # self.driver.get("https://act.qzone.qq.com/vip/2020/dnf1126")
            # time.sleep(5)
            # logger.info("OK，理论上次数应该刷新了")

        return

    def fetch_qq_video_vuserid(self):
        logger.info("转到qq视频界面，从而可以获取vuserid，用于腾讯视频的蚊子腿")
        self.driver.get("https://m.film.qq.com/magic-act/110254/index.html")
        for i in range(5):
            vuserid = self.driver.get_cookie('vuserid')
            if vuserid is not None:
                break
            time.sleep(1)
        self.add_cookies(self.driver.get_cookies())

    def try_auto_resolve_captcha(self):
        try:
            self._try_auto_resolve_captcha()
        except Exception as e:
            msg = f"ver {now_version} 自动处理验证失败了，出现未捕获的异常，请加群966403777反馈或自行解决。请手动进行处理验证码"
            logger.exception(color("fg_bold_red") + msg, exc_info=e)
            logger.warning(color("fg_bold_cyan") + "如果稳定报错，不妨打开网盘，看看是否有新版本修复了这个问题~")
            logger.warning(color("fg_bold_cyan") + "链接：https://fzls.lanzous.com/s/djc-helper")

    def _try_auto_resolve_captcha(self):
        if not self.cfg.login.auto_resolve_captcha:
            logger.info("未启用自动处理拖拽验证码的功能")
            return

        if self.cfg.login.move_captcha_delta_width_rate <= 0:
            logger.info("未设置每次尝试的偏移值，跳过自动拖拽验证码")
            return

        captcha_try_count = 0
        success_xoffset = 0
        history_key = 'history_captcha_succes_data'
        db = load_db()
        history_captcha_succes_data = db.get(history_key, {})
        try:
            WebDriverWait(self.driver, self.cfg.login.open_url_wait_time).until(expected_conditions.visibility_of_element_located((By.ID, "tcaptcha_iframe")))
            tcaptcha_iframe = self.driver.find_element_by_id("tcaptcha_iframe")
            self.driver.switch_to.frame(tcaptcha_iframe)

            logger.info(color("bold_green") + "检测到了滑动验证码，将开始自动处理。（若验证码完毕会出现短信验证，请去配置文件关闭本功能，目前暂不支持带短信验证的情况）")

            try:
                WebDriverWait(self.driver, self.cfg.login.open_url_wait_time).until(expected_conditions.visibility_of_element_located((By.ID, "slide")))
                WebDriverWait(self.driver, self.cfg.login.open_url_wait_time).until(expected_conditions.visibility_of_element_located((By.ID, "slideBlock")))
                WebDriverWait(self.driver, self.cfg.login.open_url_wait_time).until(expected_conditions.visibility_of_element_located((By.ID, "tcaptcha_drag_button")))
            except Exception as e:
                logger.warning("等待验证码相关元素出现失败了,将按照默认宽度进行操作", exc_info=e)

            drag_tarck_width = self.driver.find_element_by_id('slide').size['width'] or 280  # 进度条轨道宽度
            drag_block_width = self.driver.find_element_by_id('slideBlock').size['width'] or 56  # 缺失方块宽度
            delta_width = int(drag_block_width * self.cfg.login.move_captcha_delta_width_rate) or 11  # 每次尝试多移动该宽度

            drag_button = self.driver.find_element_by_id('tcaptcha_drag_button')  # 进度条按钮

            # 根据经验，缺失验证码大部分时候出现在右侧，所以从右侧开始尝试
            xoffsets = []
            init_offset = drag_tarck_width - drag_block_width - delta_width
            if len(history_captcha_succes_data) != 0:
                # 若有则取其中最频繁的前几个作为优先尝试项
                mostCommon = Counter(history_captcha_succes_data).most_common()
                logger.info(f"根据本地记录数据，过去运行中成功解锁次数最多的偏移值为：{mostCommon}，将首先尝试他们")
                for xoffset, success_count in mostCommon:
                    xoffsets.append(int(xoffset))
            else:
                # 没有历史数据，只能取默认经验值了
                # 有几个位置经常出现，如2/4和3/4个滑块处，优先尝试
                xoffsets.append(init_offset - 2 * (drag_block_width // 4))
                xoffsets.append(init_offset - 3 * (drag_block_width // 4))

            logger.info(
                color("bold_green") +
                f"验证码相关信息：轨道宽度为{drag_tarck_width}，滑块宽度为{drag_block_width}，偏移递增量为{delta_width}({self.cfg.login.move_captcha_delta_width_rate:.2f}倍滑块宽度)"
            )

            # 将普通序列放入其中
            xoffset = init_offset
            while xoffset > 0:
                xoffsets.append(xoffset)
                xoffset -= delta_width

            wait_time = 1

            logger.info("先release滑块一次，以避免首次必定失败的问题")
            ActionChains(self.driver).release(on_element=drag_button).perform()
            time.sleep(wait_time)

            logger.info(color("bold_green") + f"开始拖拽验证码，将依次尝试下列偏移量:\n{xoffsets}")
            for xoffset in xoffsets:
                ActionChains(self.driver).click_and_hold(on_element=drag_button).perform()  # 左键按下
                time.sleep(0.5)
                ActionChains(self.driver).move_by_offset(xoffset=xoffset, yoffset=0).perform()  # 将滑块向右滑动指定距离
                time.sleep(0.5)
                ActionChains(self.driver).release(on_element=drag_button).perform()  # 左键放下，完成一次验证尝试
                time.sleep(0.5)

                captcha_try_count += 1
                success_xoffset = xoffset
                distance_rate = (init_offset - xoffset) / drag_block_width
                logger.info(f"尝试第{captcha_try_count}次拖拽验证码，本次尝试偏移量为{xoffset}，距离右侧初始尝试位置({init_offset})距离相当于{distance_rate:.2f}个滑块宽度(若失败将等待{wait_time}秒)")

                time.sleep(wait_time)

            self.driver.switch_to.parent_frame()
        except StaleElementReferenceException as e:
            logger.info(f"成功完成了拖拽验证码操作，总计尝试次数为{captcha_try_count}")
            # 更新历史数据
            success_key = str(success_xoffset)  # 因为json只支持str作为key，所以需要强转一下，使用时再转回int
            if success_key not in history_captcha_succes_data:
                history_captcha_succes_data[success_key] = 0
            history_captcha_succes_data[success_key] += 1
            db[history_key] = history_captcha_succes_data
            save_db(db)
        except TimeoutException as e:
            logger.info("看上去没有出现验证码")

    def set_window_size(self):
        logger.info("浏览器设为1936x1056")
        self.driver.set_window_size(1936, 1056)

    def add_cookies(self, cookies):
        to_add = []
        for cookie in cookies:
            if self.get_cookie(cookie['name']) == "":
                to_add.append(cookie)

        self.cookies.extend(to_add)

    def get_cookie(self, name):
        for cookie in self.cookies:
            if cookie['name'] == name:
                return cookie['value']
        return ''

    def print_cookie(self):
        for cookie in self.cookies:
            domain, name, value = cookie['domain'], cookie['name'], cookie['value']
            print(f"{domain:20s} {name:20s} {cookie}")

    def open_url_on_start(self, url):
        chrome_default_url = 'data:,'
        while True:
            self.driver.get(url)
            # 等待一会，确保地址栏url变量已变更
            time.sleep(0.1)
            if self.driver.current_url != chrome_default_url:
                break

            logger.info(f"尝试打开网页({url})，但似乎指令未生效，当前地址栏仍为{chrome_default_url}，等待{self.cfg.login.retry_wait_time}秒后重试")
            time.sleep(self.cfg.login.retry_wait_time)


if __name__ == '__main__':
    # 读取配置信息
    load_config("config.toml", "config.toml.local")
    cfg = config()

    ql = QQLogin(cfg.common)
    account = cfg.account_configs[0]
    acc = account.account_info
    logger.warning(f"测试账号 {account.name} 的登录情况")


    def run_test(mode):
        lr = ql.login(acc.account, acc.password, login_mode=mode, name=account.name)
        # lr = ql.qr_login(login_mode=mode, name=account.name)
        logger.info(color("bold_green") + f"{lr}")


    test_all = False

    if not test_all:
        run_test(ql.login_mode_normal)
    else:
        for attr in dir(ql):
            if not attr.startswith("login_mode_"):
                continue

            mode = getattr(ql, attr)

            logger.info(f"开始测试登录模式 {mode}，请按任意键开始测试")
            input()

            run_test(mode)
