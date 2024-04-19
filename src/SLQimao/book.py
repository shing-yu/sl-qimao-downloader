from . import nullproxies, version_list, key, red, yellow, green, clear_screen
import hashlib
import random
import requests
import re
from base64 import b64decode
from Crypto.Cipher import AES  # noqa
from Crypto.Util.Padding import unpad  # noqa
import tqdm
import time
import zipfile
import os
import shutil
import datetime
# epub mode
from ebooklib import epub


class Book:
    """
    七猫小说类\n
    事实上，这不是一个仅限于类名意义的书籍类\n
    而是应该被视为一个对于某本七猫小说的程序操作实例\n
    注意：下载过程中使用了tqdm显示进度条，如果不需要显示进度条，请自行修改\n
    :param book_id: 小说ID
    :param proxies: 代理，默认无代理
    """
    def __init__(self, book_id: str, proxies: dict = nullproxies) -> None:
        """
        使用小说ID初始化Book对象
        :param book_id:
        """
        self.book_id: str = book_id                 # 小说ID
        self.proxies: dict = proxies                # 代理
        self.version_list: list = version_list      # app版本列表
        self.key: str = key                         # 签名key
        self.headers: dict = self._get_headers()    # 请求头
        self.title: str = "None"                    # 小说标题
        self.author: str = "None"                   # 作者
        self.intro: str = "None"                    # 简介
        self.words_num: int = 0                     # 字数
        self.tags: str = "None"                     # 标签
        self.basecontent: str = "None"              # 基础内容（仅txt模式）
        self.img_url: str = "None"                  # 封面图片链接（仅epub模式）
        self.catalog: list = []                     # 目录
        self.lastcid: str = "None"                  # 最后一个章节ID
        self.file_path: str = "None"                # 保存后文件路径
        self.encoding: str = "utf-8"                # 文件编码（仅txt模式）

    def _get_headers(self) -> dict:
        """
        根据小说ID生成请求头
        :return: 请求头
        """
        # 使用小说ID作为随机种子
        random.seed(self.book_id)
        # 随机选择一个版本
        version = random.choice(self.version_list)

        headers = {
            "AUTHORIZATION": "",
            "app-version": f"{version}",
            "application-id": "com.****.reader",
            "channel": "unknown",
            "net-env": "1",
            "platform": "android",
            "qm-params": "",
            "reg": "0",
        }

        # 获取 headers 的所有键并排序
        keys = sorted(headers.keys())

        # 生成待签名的字符串
        sign_str = ''.join([k + '=' + str(headers[k]) for k in keys]) + self.key

        # 生成签名
        headers['sign'] = hashlib.md5(sign_str.encode()).hexdigest()

        return headers

    def _sign(self, params: dict) -> dict:
        """
        原名: sign_url_params\n
        签名url参数
        :param params: url参数
        :return: 签名后的url参数
        """
        keys = sorted(params.keys())

        # 生成待签名的字符串
        sign_str = ''.join([k + '=' + str(params[k]) for k in keys]) + self.key

        # 使用MD5哈希生成签名
        signature = hashlib.md5(sign_str.encode()).hexdigest()

        # 将签名添加到参数字典中
        params['sign'] = signature

        return params

    @staticmethod
    def _rename(name: str) -> str:
        """
        替换将要作为文件名的小说/章节名中的非法字符
        :param name: 原名
        :return: 替换后的名字
        """
        # 定义非法字符的正则表达式模式
        illegal_characters_pattern = r'[\/:*?"<>|]'

        # 定义替换的中文符号
        replacement_dict = {
            '/': '／',
            ':': '：',
            '*': '＊',
            '?': '？',
            '"': '“',
            '<': '＜',
            '>': '＞',
            '|': '｜'
        }

        # 使用正则表达式替换非法字符
        new_name = re.sub(illegal_characters_pattern, lambda x: replacement_dict[x.group(0)], name)

        return new_name

    @staticmethod
    def _decrypt(origin: str) -> str:
        """
        解密被加密的文本
        :param origin: 被加密的文本
        :return: 解密后的文本
        """
        # 七猫使用AES加密
        txt = b64decode(origin)
        iv = txt[:16].hex()
        data = txt[16:].hex()
        dkey = bytes.fromhex('32343263636238323330643730396531')
        iv = bytes.fromhex(iv)
        cipher = AES.new(dkey, AES.MODE_CBC, iv=iv)
        decrypted = unpad(cipher.decrypt(bytes.fromhex(data)), AES.block_size)
        decrypted = decrypted.decode('utf-8').strip()
        return decrypted

    def get_info(self) -> None:
        """
        获取小说信息
        :return: None
        """
        # 请求API
        info = requests.get(f"https://api-bc.wtzw.com/api/v1/reader/detail?id={self.book_id}", proxies=self.proxies,
                            timeout=12).json()

        # 提取信息
        self.title = self._rename(info["data"]["title"])
        self.author = info["data"]["author"]
        self.intro = info["data"]["intro"]
        self.words_num = info["data"]["words_num"]
        tags = [tag["title"] for tag in info["data"]["book_tag_list"]]
        self.tags = str(tags).replace("'", "").replace("[", "").replace("]", "")

        self.basecontent = f"""如果需要小说更新，请勿修改文件名
使用 @星隅(shing-yu) 所作开源星弦下载器七猫版v4下载
开源仓库地址:https://github.com/shing-yu/7mao-novel-downloader
Gitee:https://gitee.com/xingyv1024/7mao-novel-downloader/
任何人无权限制您访问本工具，如果有向您提供代下载服务者未事先告知您工具的获取方式，请向作者举报:xing_yv@outlook.com

名称：{self.title}
作者：{self.author}
标签：{self.tags}
简介：{self.intro}
字数：{self.words_num}
书籍ID：{self.book_id}
"""
        self.img_url = info["data"]["image_link"]
        return

    def get_catalog(self) -> None:
        """
        获取小说目录
        :return: None
        """
        # 请求章节列表
        params = {
            'chapter_ver': '0',
            'id': self.book_id,
        }
        response = requests.get("https://api-ks.wtzw.com/api/v1/chapter/chapter-list",
                                params=self._sign(params),
                                headers=self.headers,
                                proxies=self.proxies,
                                timeout=12).json()

        # {
        #     "data": {
        #         "id": "1784910",
        #         "type": "chapter_lists",
        #         "chapter_lists": [
        #             {
        #                 "id": "17059219910001",
        #                 "content_md5": "bac8397a6dc95bbfdacbde5b60f9e345",
        #                 "index": "1",
        #                 "title": "第一章 离乡",
        #                 "words": "5968",
        #                 "chapter_sort": 1
        #             },

        chapters: list = response["data"]["chapter_lists"]
        # 使用chapter_sort排序
        chapters.sort(key=lambda x: x["chapter_sort"])

        self.catalog = chapters

    class DownloadCacheError(Exception):
        """
        下载缓存文件错误
        """

        def __init__(self, message: str) -> None:
            self.message = message
            super().__init__(self.message)

    def _gaunade(self) -> list:
        """
        原名: get_and_unzip_and_decrypt\n
        获取、解压、解密缓存文件\n
        返回一个列表对象，该对象是一个文件夹内文件的列表，文件夹内含解密后的小说内容\n
        生成一个以小说ID命名的文件夹，内含解密后的小说内容
        :return: 一个os.walk对象
        """
        # 4.0新增调用官方缓存接口
        params = {
            'id': self.book_id,
            'source': 1,
            'type': 2,
            'is_vip': 1
        }
        # 请求全本缓存接口得到下载链接
        response = requests.get("https://api-bc.wtzw.com/api/v1/book/download",
                                params=self._sign(params),
                                headers=self.headers,
                                proxies=self.proxies,
                                timeout=12).json()
        link = response["data"]["link"]
        # 创建临时文件
        temp = f"{self.book_id}.zip"
        try:
            print("开始下载缓存文件")
            # 请求zip文件
            response = requests.get(link, stream=True)
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024
            # 下载进度
            with tqdm.tqdm(total=total_size // block_size, unit='KB', unit_scale=True, desc="正在下载缓存文件") as pbar:
                with open(temp, 'wb') as f:
                    for data in response.iter_content(block_size):
                        pbar.update(1)
                        f.write(data)
                        time.sleep(0.003)  # 限速约300KB/s
            print(green + f"下载缓存文件成功")
        except Exception as e:
            raise self.DownloadCacheError(f"下载缓存文件失败：{e}")

        # 解压缓存文件
        print("开始解压缓存文件")
        os.makedirs(self.book_id, exist_ok=True)
        with zipfile.ZipFile(temp, 'r') as z:
            z.extractall(self.book_id)
        print(green + f"解压缓存文件成功")

        # 删除临时文件
        os.remove(temp)

        txts = os.listdir(self.book_id)
        txts = [os.path.join(self.book_id, txt) for txt in txts]

        print(yellow + "本程序开源免费，如果您遇到收费情况，请立即退款并举报商家")

        # 解密缓存文件
        print("开始解密缓存文件")
        for file in txts:
            with open(file, 'r+', encoding='utf-8') as f:
                content = f.read()
                f.seek(0)
                f.truncate()
                f.write(self._decrypt(content))
        print(green + f"解密缓存文件成功")
        return txts

    def write_update(self, datafolder: str) -> None:
        """
        写入更新元数据文件（仅txt模式）\n
        注意：此方法仅为兼容旧版本和将文件名对应为书籍ID存在的情况，如只使用新版本，已无需调用此方法\n
        如只使用新版本，已无需调用此方法
        :param datafolder: 程序数据文件夹路径
        :return: None
        """
        if self.lastcid == "None":
            print(red + "该下载模式不支持写入更新元数据文件或未调用下载方法")
            return
        # 计算hash
        hash_sha256 = hashlib.sha256()
        with open(self.file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        sha256_hash = hash_sha256.hexdigest()
        # 创建更新元数据文件
        with open(os.path.join(datafolder, f"{self.title}.upd"), 'w', encoding='utf-8') as f:
            f.write(f"""{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{self.book_id}
{self.lastcid}
{self.encoding}
{sha256_hash}""")
        return

    def totxt(self, path: str, encoding: str = "utf-8", start: str = "None") -> None:
        """
        下载小说到txt文件\n
        注意：该方法保存为一个txt文件，分章节保存请使用totxt_ecs方法\n
        就算指定了起始章节ID，程序仍然会完整下载文件，只是在合并时会从指定章节开始，并不能带来下载速度提升\n
        :param path: txt文件保存路径
        :param encoding: 编码，默认utf-8
        :param start: 起始章节ID，默认None
        :return: None
        """
        # if start != "None":
        #     print(yellow + "注意：指定了起始章节ID，程序仍然会完整下载文件，只是在合并时会从指定章节开始，并不能带来下载速度提升")
        # else:
        #     start = None
        if self.title == "None":
            print(red + "请先调用ready方法获取小说信息和目录")
            return
        if start == "None":
            start = None
        self.encoding = encoding
        # 调用获取、解压、解密缓存文件方法
        txts = self._gaunade()

        # 合并txt文件
        print("开始合并文件")
        if len(self.catalog) != len(txts):
            print(red + f"章节数量不匹配，无法合并文件：{len(self.catalog)}章/{len(txts)}章")
            print(red + "合并文件失败")
            return
        hide_index = self.catalog[len(self.catalog[self.catalog.index(start) if start is not None else 0:]) // 2]['id']
        hide_content = """\n\n\n该小说通过星隅开发的开源免费星弦下载器下载
如果您通过代下载获取该小说文件，且商家未提供软件源代码或开源地址，请立即退款并举报商家
作者邮箱：xing_yv@outlook.com
作者QQ：2017593710
官方QQ交流群：149050832
官方TG交流群：https://t.me/FQTool\n\n\n
"""
        self.file_path = os.path.join(path, f"{self.title}.txt")
        with open(self.file_path, 'w', encoding=encoding, errors='ignore') as f:
            start_flag = False
            f.write(self.basecontent)
            for file, chapter in tqdm.tqdm(zip(txts, self.catalog), desc="合并进度", unit="章"):
                if start is not None:
                    if chapter['id'] == start:
                        start_flag = True
                    if not start_flag:
                        continue
                with open(file, 'r', encoding='utf-8') as txt:
                    f.write(f"\n\n\n{chapter['title']}\n\n{txt.read()}")
                if chapter['id'] == hide_index:
                    f.write(hide_content)
                self.lastcid = chapter['id']
        if start is not None and not start_flag:
            print(red + f"起始章节ID{start}不存在")
            print(red + "合并文件失败")
            return
        shutil.rmtree(self.book_id)
        print(green + f"合并文件成功，小说共{len(self.catalog)}章")
        if start is not None:
            print(green + f"从章节ID{start}开始合并")
        print(green + f"小说《{self.title}》已下载完成" + '-'*20)
        return

    def totxt_ecs(self, path: str, encoding: str = "utf-8", start: str = "None") -> None:
        """
        下载小说到txt文件，分章节保存\n
        注意：该方法保存为多个txt文件，合并为一个请使用totxt方法\n
        :param path: txt文件保存路径
        :param encoding: 编码，默认utf-8
        :param start: 起始章节ID，默认None（不支持，将在未来移除）
        :return: None
        """
        if self.title == "None":
            print(red + "请先调用ready方法获取小说信息和目录")
            return
        if start != "None":
            print(yellow + "注意：分章模式不支持指定起始章节ID，请手动删除不需要的章节文件")
        if encoding != 'utf-8':
            print(yellow + "注意：使用非utf-8编码可能会导致处理速度变慢")
        self.encoding = encoding
        # 调用获取、解压、解密缓存文件方法
        txts = self._gaunade()

        # 合并txt文件
        print("开始处理文件")
        if len(self.catalog) != len(txts):
            print(red + f"章节数量不匹配，无法处理文件：{len(self.catalog)}章/{len(txts)}章")
            print(red + "处理文件失败")
            return
        path = os.path.join(path, self.title)
        os.makedirs(path, exist_ok=True)
        hide_index = self.catalog[len(self.catalog) // 2]['id']
        hide_content = """\n\n\n该小说通过星隅开发的开源免费星弦下载器下载
如果您通过代下载获取该小说文件，且商家未提供软件源代码或开源地址，请立即退款并举报商家
作者邮箱：xing_yv@outlook.com
作者QQ：2017593710
官方QQ交流群：149050832
官方TG交流群：https://t.me/FQTool\n\n\n
"""
        with open(os.path.join(path, "简介.txt"), 'w', encoding=encoding) as f:
            f.write(self.basecontent)
        for file, chapter in tqdm.tqdm(zip(txts, self.catalog), desc="处理进度", unit="章"):
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(os.path.join(path, f"{self._rename(chapter['title'])}.txt"), 'w', encoding=encoding,
                      errors='ignore') as f:
                f.write(content)
                if chapter['id'] == hide_index:
                    f.write(hide_content)

        shutil.rmtree(self.book_id)
        print(green + f"处理文件成功，小说共{len(self.catalog)}章")
        print(green + f"小说《{self.title}》已下载完成" + '-'*20)
        return

    def toepub(self, path: str, **kwargs) -> None:
        """
        下载小说到epub文件（暂未实现）\n
        **kwargs: 传入字体与css文件路径\n
        字体路径格式: font*=path\n
        css路径格式: css*=path\n
        *: 任意 path: 文件路径\n
        :param path: epub文件保存路径
        :param kwargs: 字体与css文件路径（可选）
        :return: None
        """
        if self.title == "None":
            print(red + "请先调用ready方法获取小说信息和目录")
            return
        txts = self._gaunade()
        # 创建电子书对象
        book = epub.EpubBook()
        # 获取封面
        cover = requests.get(self.img_url, proxies=self.proxies, timeout=10).content
        # 创建封面
        book.set_cover("image.jpg", cover)

        # 设置元数据
        book.set_title(self.title)
        book.set_language('zh-CN')
        book.add_author(self.author)
        book.add_metadata('DC', 'description', self.intro)
        # 写入book_id
        book.add_metadata('DC', 'bookid', self.book_id)

        # 读取资源文件
        fonts: list = []
        css: list = []
        for key_, value in kwargs.items():
            if key_.startswith("font"):
                fonts.append(value)
            elif key_.startswith("css"):
                css.append(value)
        # 添加字体文件
        for i, font in enumerate(fonts):
            with open(font, 'rb') as f:
                font_content = f.read()
            mimetype = "application/octet-stream"
            # match font.split('.')[-1]:
            #     case 'ttf':
            #         mimetype = "application/vnd.ms-opentype"
            #     case 'otf':
            #         mimetype = "application/vnd.ms-opentype"
            #     case 'woff2':
            #         print(red + "警告：woff2字体虽然存在于epub3规范中，但是可能不被所有阅读器支持")
            #         mimetype = "font/woff2"
            #     case _:
            #         print(red + "警告：未知字体格式，可能导致阅读器无法识别")
            if font.endswith('.ttf'):
                mimetype = "application/vnd.ms-opentype"
            elif font.endswith('.otf'):
                mimetype = "application/vnd.ms-opentype"
            elif font.endswith('.woff2'):
                print(red + "警告：woff2字体虽然存在于epub3规范中，但是可能不被所有阅读器支持")
                mimetype = "font/woff2"
            else:
                print(red + "警告：未知字体格式，可能导致阅读器无法识别")
            book.add_item(epub.EpubItem(
                uid=f"font{i}", file_name=f"fonts/{os.path.basename(font)}",
                media_type=mimetype,
                content=font_content
            ))
        # 添加css文件
        cssitems = []
        for i, css_file in enumerate(css):
            with open(css_file, 'r', encoding='utf-8') as f:
                css_content = f.read()
            cssitem = epub.EpubItem(
                uid=f"css{i}", file_name=f"styles/{os.path.basename(css_file)}",
                media_type="text/css", content=css_content
            )
            book.add_item(cssitem)
            cssitems.append(cssitem)

        # 简介章节
        intro_e = epub.EpubHtml(title='Introduction', file_name='intro.xhtml', lang='zh-CN')
        for cssitem in cssitems:
            intro_e.add_item(cssitem)
        intro_e.content = (f'<img src="image.jpg" alt="Cover Image"/>'
                           f'<h1>{self.title}</h1>'
                           f'<p>{self.intro}</p>')
        book.add_item(intro_e)
        # 创建索引
        book.toc = (epub.Link('intro.xhtml', '简介', 'intro'),)
        book.spine = ['nav', intro_e]
        # 定义目录索引
        toc_index = ()
        chapter_id_name = 0

        if len(self.catalog) != len(txts):
            print(red + f"章节数量不匹配，无法处理文件：{len(self.catalog)}章/{len(txts)}章")
            print(red + "处理文件失败")
            return

        hide_index = self.catalog[len(self.catalog) // 2]['id']
        hide_content = """</p><br><p>该小说通过星隅开发的开源免费星弦下载器下载</p>
<p>如果您通过代下载获取该小说文件，且商家未提供软件源代码或开源地址，请立即退款并举报商家</p>
<p>作者邮箱：xing_yv@outlook.com</p>
<p>作者QQ：2017593710</p>
<p>官方QQ交流群：149050832</p>
<p>官方TG交流群：https://t.me/FQTool</p><br><p>
"""

        # 添加章节
        for file, chapter in tqdm.tqdm(zip(txts, self.catalog), desc="正在添加章节", unit="章"):
            chapter_id_name += 1
            with open(file, 'r', encoding='utf-8') as f:
                chapter_content = f.read()
            # 转换文本格式
            chapter_text = re.sub(r'\n', '</p><p>', chapter_content)
            if chapter['id'] == hide_index:
                chapter_text += hide_content
            # 创建章节实例
            text = epub.EpubHtml(title=chapter['title'], file_name=f'chapter_{chapter_id_name}.xhtml', lang='zh-CN')
            for cssitem in cssitems:
                text.add_item(cssitem)
            text.content = (f'<h2 class="titlecss">{chapter["title"]}</h2>'
                            f'<p>{chapter_text}</p>')
            # 加入索引
            toc_index += (text, )
            book.spine.append(text)
            book.add_item(text)
        # 加入书籍索引
        book.toc += toc_index

        # 添加navigation文件
        nav_file = epub.EpubNav()
        for cssitem in cssitems:
            nav_file.add_item(cssitem)
        book.add_item(epub.EpubNcx())
        book.add_item(nav_file)
        # 保存epub文件
        epub.write_epub(os.path.join(path, f"{self.title}.epub"), book)
        shutil.rmtree(self.book_id)
        print(green + f"生成epub文件成功，小说共{len(self.catalog)}章")
        print(green + f"小说《{self.title}》已下载完成" + '-'*20)
        return

    @staticmethod
    def update() -> None:
        """
        由于4.0版本的下载机制的底层变动，更新功能已经被弃用\n
        将在未来版本中移除此方法
        :return: None
        """
        print(red + "由于4.0版本的下载机制的底层变动，更新功能已经被弃用")
        return

    def ready(self) -> None:
        """
        准备下载\n
        该方法用于准备下载，包括获取小说信息和目录
        :return: None
        """
        self.get_info()
        self.get_catalog()
        return


def sign_url(params: dict) -> dict:
    """
    原名: sign_url_params\n
    签名url参数\n
    由类Book的_sign方法独立出来的函数
    :param params: url参数
    :return: 签名后的url参数
    """
    keys = sorted(params.keys())

    # 生成待签名的字符串
    sign_str = ''.join([k + '=' + str(params[k]) for k in keys]) + key

    # 使用MD5哈希生成签名
    signature = hashlib.md5(sign_str.encode()).hexdigest()

    # 将签名添加到参数字典中
    params['sign'] = signature

    return params


def get_headers(book_id) -> dict:
    """
    根据小说ID生成请求头\n
    由类Book的_get_headers方法独立出来的函数
    :param book_id: 小说ID
    :return: 请求头
    """
    # 使用小说ID作为随机种子
    random.seed(book_id)
    # 随机选择一个版本
    version = random.choice(version_list)

    headers = {
        "AUTHORIZATION": "",
        "app-version": f"{version}",
        "application-id": "com.****.reader",
        "channel": "unknown",
        "net-env": "1",
        "platform": "android",
        "qm-params": "",
        "reg": "0",
    }

    # 获取 headers 的所有键并排序
    keys = sorted(headers.keys())

    # 生成待签名的字符串
    sign_str = ''.join([k + '=' + str(headers[k]) for k in keys]) + key

    # 生成签名
    headers['sign'] = hashlib.md5(sign_str.encode()).hexdigest()

    return headers


def search() -> str | None:
    """
    搜索小说\n
    注意：此函数为交互式函数，不应在非交互式环境中使用\n
    :return: 用户选择的小说ID，或者None
    """
    try:
        while True:

            key_ = input("请输入搜索关键词（按下Ctrl+C返回）：")

            # 获取搜索结果列表
            params_ = {
                'extend': '',
                'tab': '0',
                'gender': '0',
                'refresh_state': '8',
                'page': '1',
                'wd': f'{key_}',
                'is_short_story_user': '0'
            }
            response = requests.get("https://api-bc.wtzw.com/search/v1/words", params=sign_url(params_),
                                    headers=get_headers("00000000"), timeout=10).json()
            books = response['data']['books']

            for i, book in enumerate(books):
                try:
                    print(f"{i + 1}. 名称：{book['original_title']} 作者：{book['original_author']} "
                          f"ID：{book['id']} 字数：{book['words_num']}")
                except KeyError:
                    break

            while True:
                choice_ = input("请选择一个结果, 输入r以重新搜索：")
                if choice_ == "r":
                    clear_screen()
                    break
                elif choice_.isdigit():
                    choice = int(choice_)
                    if choice > len(books):
                        print("输入无效，请重新输入。")
                        continue
                    chosen_book = books[choice - 1]
                    book_id = chosen_book['id']
                    return book_id
                else:
                    print("输入无效，请重新输入。")
                    continue
    except KeyboardInterrupt:
        return
