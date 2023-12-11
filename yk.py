import os
import re, requests, time, json
from hashlib import md5
from urllib.parse import parse_qsl, urlsplit
import base64
from Crypto.Cipher import AES
from tabulate import tabulate
from pywidevine.L3.cdm import deviceconfig
from pywidevine.L3.decrypt.wvdecryptcustom import WvDecrypt
from tools import get_pssh, dealck

requests = requests.Session()


class YouKu:
    def __init__(self, cookie):
        self.cookie = dealck(cookie)
        self.r = "xWrtQpP4Z4RsrRCY"
        self.R = "aq1mVooivzaolmJY5NrQ3A=="
        self.key = ""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
        }
        requests.headers.update(self.headers)
        requests.cookies.update(self.cookie)
        self.ptoken = self.cookie.get("P_pck_rm")
        self.utida = "ZIH81OVlRSMDAOQQiG52i4cO"

    def youku_sign(self, t, data, token):
        appKey = '24679788'  # 固定值
        '''token值在cookie中'''
        sign = token + '&' + t + '&' + appKey + '&' + data
        md = md5()
        md.update(sign.encode('UTF-8'))
        sign = md.hexdigest()
        return sign

    def utid(self):
        json_cookie = requests.cookies.get_dict()
        requests.cookies.clear()
        requests.cookies.update(json_cookie)
        utid = json_cookie.get("cna")
        token = json_cookie.get("_m_h5_tk").split("_")[0]
        return {"utid": utid, "token": token}

    # 若直接在首页小窗口上复制的视频网址，是重定向的网址。
    def redirect(self, url):
        headers = {
            "referer": "https://www.youku.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
        }
        resp = requests.get(url=url)
        return resp.url

    def page_parser(self, url):
        vid = re.findall(r"id_(.*?)\.html", url)[0]
        url = "https://openapi.youku.com/v2/videos/show.json"
        params = {
            "client_id": "53e6cc67237fc59a",
            "package": "com.huawei.hwvplayer.youku",
            "ext": "show",
            "video_id": vid
        }
        try:
            response = requests.get(url, params=params).json()
            showid = response["show"]["id"]
            return {"current_showid": showid, "videoId": 0, "vid": vid}
        except Exception as e:
            print(f"获取showid失败:{e}")
            print(f"[red]获取showid失败[/red]")

    def get_emb(self, videoId):
        emb = base64.b64encode(("%swww.youku.com/" % videoId).encode('utf-8')).decode('utf-8')
        return emb

    # 这个函数用来获取元素的第一个值
    def takeOne(self, elem):
        return float(elem[0])

    def save_m3u8(self, video, auto=1):
        title, size, resolution, drm_type, key, stream_type, _, m3u8_url, _ = video
        title = f"{title}_{resolution}_{size}_{stream_type}"
        savepath = os.path.join(os.getcwd(), "/download/yk")
        rm3u8_url = m3u8_url.replace("%", "%%")
        if rm3u8_url.startswith("http"):
            common_args = f"N_m3u8DL-RE.exe \"{rm3u8_url}\" --tmp-dir ./cache --save-name \"{title}\" --save-dir \"{savepath}\" --thread-count 16 --download-retry-count 30  --check-segments-count"
            if auto:
                common_args += " --auto-select"
            if drm_type == "default":
                cmd = common_args
            elif drm_type == "cbcs":
                cmd = f"{common_args} --key {key}  -M format=mp4"
            else:
                key = key if ":" not in key else base64.b64encode(bytes.fromhex(key.split(":")[1])).decode()
                txt = f'''
            #OUT,{savepath}
            #DECMETHOD,ECB
            #KEY,{key}
            {title},{m3u8_url}
                                '''
                with open("{}.txt".format(title), "a", encoding="gbk") as f:
                    f.write(txt)
                    print("下载链接已生成")
                    return
        else:
            m3u8_path = "{}.m3u8".format(title)
            with open(m3u8_path, "w", encoding="utf-8") as f:
                f.write(m3u8_url)
            if ":" not in key:
                uri = re.findall(r'URI="(.*)"', m3u8_url)[0]
                m3u8_text = requests.get(uri).text
                keyid = re.findall(r'KEYID=0x(.*),IV', m3u8_text)[0].lower()
                key = "{}:{}".format(keyid, base64.b64decode(key).hex())
            common_args = f"N_m3u8DL-RE.exe \"{m3u8_path}\" --tmp-dir ./cache --save-name \"{title}\" --save-dir \"{savepath}\" --thread-count 16 --download-retry-count 30  --check-segments-count"
            cmd = f"{common_args} --key {key}  -M format=mp4"
        with open("{}.bat".format(title), "a", encoding="gbk") as f:
            f.write(cmd)
            f.write("\n")
        f.close()
        print("下载链接已生成")

    def m3u8_url(self, t, params_data, sign, vid):
        url = "https://acs.youku.com/h5/mtop.youku.play.ups.appinfo.get/1.1/"

        params = {
            "jsv": "2.5.8",
            "appKey": "24679788",
            "t": t,
            "sign": sign,
            "api": "mtop.youku.play.ups.appinfo.get",
            "v": "1.1",
            "timeout": "20000",
            "YKPid": "20160317PLF000211",
            "YKLoginRequest": "true",
            "AntiFlood": "true",
            "AntiCreep": "true",
            "type": "jsonp",
            "dataType": "jsonp",
            "callback": "mtopjsonp1",
            "data": params_data,
        }
        resp = requests.get(url=url, params=params)
        result = resp.text
        # print(result)
        data = json.loads(result[12:-1])
        # print(data)
        ret = data["ret"]
        video_lists = []
        if ret == ["SUCCESS::调用成功"]:
            stream = data["data"]["data"].get("stream", [])
            title = data["data"]["data"].get("video", {}).get("title", "")
            print("解析成功:")
            keys = {}
            tv_stream = self.get_TV_stream(vid)
            stream.extend(tv_stream)
            for video in stream:
                m3u8_url = video["m3u8_url"]
                width = video["width"]
                height = video["height"]
                size = video.get("size", 0)
                size = '{:.1f}'.format(float(size) / 1048576)
                drm_type = video["drm_type"]
                audio_lang = video["audio_lang"]
                audio = video['stream_ext'].get("audioGroupId", "")
                if audio_lang == "default":
                    audio_lang = "guoyu"
                language = []
                language = re.findall(r'LANGUAGE="([\w\s]+)"', m3u8_url)
                # print("language是------------------>>>>>", language)
                if 'en' in language:
                    audio_lang = "en"
                if video['drm_type'] == "default":
                    key = ""
                elif audio_lang not in keys.keys():
                    if drm_type == "cbcs":
                        license_url = video["stream_ext"]["uri"]
                        key = self.get_cbcs_key(license_url, m3u8_url)
                        if key[0]:
                            key = key[1][0]
                    else:
                        encryptR_server = video['encryptR_server']
                        copyright_key = video['stream_ext']['copyright_key']
                        key = self.copyrightDRM(self.r, encryptR_server, copyright_key)
                    keys[audio_lang] = key
                else:
                    key = keys[audio_lang]
                if audio == "":
                    lang = audio_lang
                else:
                    lang = audio + "_" + audio_lang
                video_lists.append(
                    [title, size + "M", f"{width}x{height}", drm_type, key, video["stream_type"],
                     lang, m3u8_url,
                     video.get("size", 0)])
            video_lists = sorted(video_lists, key=lambda x: x[-1], reverse=True)
            tb = tabulate([[*video_lists[i][:7]] for i in range(len(video_lists))],
                          headers=["标题", "分辨率", "视频大小", "drm_type", "base64key", "stream_type", "audio"],
                          tablefmt="pretty",
                          showindex=range(1, len(video_lists) + 1))
            ch = input(f"{tb}\n请输入要下载的视频序号,输入0尝试自动选择最高清晰度视频：")
            if ch == "0":
                self.save_m3u82(video_lists)
                return 0
            ch = ch.split(",")
            for i in ch:
                video = video_lists[int(i) - 1]
                self.save_m3u8(video)
        elif ret == ["FAIL_SYS_ILLEGAL_ACCESS::非法请求"]:
            print("请求参数错误")
        elif ret == ["FAIL_SYS_TOKEN_EXOIRED::令牌过期"]:
            print("Cookie过期")
            return 10086
        else:
            print(ret[0])
        return 0

    def copyrightDRM(self, r, encryptR_server, copyright_key):
        try:
            crypto_1 = AES.new(r.encode(), AES.MODE_ECB)
            key_2 = crypto_1.decrypt(base64.b64decode(encryptR_server))
            crypto_2 = AES.new(key_2, AES.MODE_ECB)
            return base64.b64encode(base64.b64decode(crypto_2.decrypt(base64.b64decode(copyright_key)))).decode()
        except:
            return ""

    def get_cbcs_key(self, license_url, m3u8_url):
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.82"
        }
        m3u8data = requests.get(m3u8_url, headers=headers).text
        key_url = re.findall(r"URI=\"(.*?)\"", m3u8data)[0]
        response = requests.get(key_url, headers=headers).text
        pssh = response.split("data:text/plain;base64,").pop().split('",')[0]
        wvdecrypt = WvDecrypt(init_data_b64=pssh, cert_data_b64="", device=deviceconfig.device_android_generic)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.82",
        }
        dic = dict(parse_qsl(urlsplit(license_url).query))
        url = license_url.split("?")[0]
        dic["licenseRequest"] = base64.b64encode(wvdecrypt.get_challenge()).decode()
        dic["drmType"] = "widevine"
        response = requests.post(url, data=dic, headers=headers)
        license_b64 = response.json()["data"]
        wvdecrypt.update_license(license_b64)
        Correct, keyswvdecrypt = wvdecrypt.start_process()
        if Correct:
            return Correct, keyswvdecrypt

    def get_TV_stream(self, vid):
        headers = {
            "user-agent": "OTTSDK;1.0.8.6;Android;9;2203121C"
        }

        def getdata():
            response = requests.get(url, headers=headers, params=params)
            try:
                data = response.json()["data"]
                title = data['show']["title"]
                streams = data["stream"]
                streamss.extend(streams)
                return title, streams
            except Exception as e:
                return None, []

        url = "https://ups.youku.com/ups/get.json"  # light_get.json
        params = {
            "ckey": "7B19C0AB12633B22E7FE81271162026020570708D6CC189E4924503C49D243A0DE6CD84A766832C2C99898FC5ED31F3709BB3CDD82C96492E721BDD381735026",
            "client_ip": "192.168.3.1",
            "client_ts": "1697343919",
            "utid": self.utida,
            "pid": "36281532078091",
            # HAIER_PID = "36214723575196"; JIMI_PID = "3b777e6ae3c99e26";SONY_PID = "36281532078091";
            "player_type": "dnahard",  # system:hls,dnahard: cmfv
            "app_ver": "11.4.6.4",  # 2121104604,2121100600,11.0.6.0,11.4.6.4
            "ccode": "0103010261",  # sony :0103010261, jimi:010301025C,haier:0103010275 280
            "player_source": "21",  # 20 sdr 21hfr 22dolby 23bit10
            "encryptR_client": "fTWuKHLOVUoOide+VH/h8w==",
            "key_index": "key01",
            "vid": vid,
            "h265": "1",
            "media_type": "standard,sei",
            "client_id": "",
            "ptoken": self.ptoken,
            "drm_type": "7",
            "extag": "EXT-X-PRIVINF",
            "extag_fields": "STREAMTYPE",
            "device_name": "XR-98X90L",
            "play_ability": "405929984",
            "preferClarity": "23",
            "master_m3u8": "0",
            "play_ability_v2": "2222222",
            "site": "1",
            "fu": "1",
            "vs": "1.0",
            "os": "android",
            "osv": "12.1.1",
            "bt": "tv",
            "aw": "a",
            "p": "27",
            "mdl": "XR-98X90L",
            "device_model": "XR-98X90L",
            "": ""
        }
        streamss = []
        player_source = [20, 23, 22, 21]
        player_type = ["system", "dnahard"]
        for i in player_source:
            params["player_source"] = str(i)
            for j in player_type:
                params["player_type"] = j
                getdata()
        params["ccode"] = "0103010275"
        params["player_source"] = "21"
        params["player_type"] = "system"
        getdata()
        url = "https://ups.youku.com/ups/get.json"
        params['ccode'] = '0103010102'
        params.update({"app_ver": "2121104604",
                       "play_ability": "536870911",
                       "play_ability_v2": "1111111",
                       "pid": "52f8ca2b4982124b", })
        play_ability_v2 = [1222221, 1222211, 1222121, 1221221, 1212221, 1122221]
        for v2 in play_ability_v2:
            params["play_ability_v2"] = v2
            getdata()
        url = "https://ups.youku.com/ups/light_get.json"
        params["ccode"] = "0103010280"
        params["drm_type"] = 0
        getdata()
        streamss = sorted(streamss, key=lambda x: x["size"], reverse=True)
        return streamss

    def get(self, url):
        t = str(int(time.time() * 1000))
        user_info = self.utid()
        userid = user_info["utid"]
        page_info = self.page_parser(url)
        emb = self.get_emb(page_info["videoId"])
        steal_params = {
            "ccode": "0502",
            "utid": userid,
            "version": "9.4.39",
            "ckey": "DIl58SLFxFNndSV1GFNnMQVYkx1PP5tKe1siZu/86PR1u/Wh1Ptd+WOZsHHWxysSfAOhNJpdVWsdVJNsfJ8Sxd8WKVvNfAS8aS8fAOzYARzPyPc3JvtnPHjTdKfESTdnuTW6ZPvk2pNDh4uFzotgdMEFkzQ5wZVXl2Pf1/Y6hLK0OnCNxBj3+nb0v72gZ6b0td+WOZsHHWxysSo/0y9D2K42SaB8Y/+aD2K42SaB8Y/+ahU+WOZsHcrxysooUeND",
            "client_ip": "192.168.1.1",
            "client_ts": 1698373135
        }
        biz_params = {
            "vid": page_info["vid"],
            "h265": 1,
            "preferClarity": 4,
            "media_type": "standard,subtitle",
            "app_ver": "9.4.39",
            "extag": "EXT-X-PRIVINF",
            "play_ability": 16782592,
            "master_m3u8": 1,
            "drm_type": 19,
            "key_index": "web01",
            "encryptR_client": self.R,
            "skh": 1,
            "last_clarity": 5,
            "clarity_chg_ts": 1689341442
        }
        ad_params = {
            "vip": 1,
        }
        params_data = {
            "steal_params": json.dumps(steal_params),
            "biz_params": json.dumps(biz_params),
            "ad_params": json.dumps(ad_params),
        }
        params_data = json.dumps(params_data)
        sign = self.youku_sign(t, params_data, user_info["token"])
        return self.m3u8_url(t, params_data, sign, page_info["vid"])

    def start(self, url=None):
        url = input("请输入视频链接：") if url is None else url
        url = self.redirect(url) if url.startswith("https://") else f"https://v.youku.com/v_show/id_{url}.html"
        for i in range(3):
            ret = self.get(url)
            if ret:
                continue
            break

    def save_m3u82(self, video_lists):
        a = []
        b = set()
        for video in video_lists:
            audio_combination = video[6]
            if audio_combination not in b:
                a.append(video)
                b.add(audio_combination)
        c = [x for x in a if "cmfv5hd" in x[5]]
        if c:
            m3u8data = "#EXTM3U\n"
            for i in range(len(c)):
                m3u8_url = c[i][-2]
                if i == 0:
                    m3u8_url = "\n".join(m3u8_url.split("\n")[1:5])
                else:
                    m3u8_url = "\n".join(m3u8_url.split("\n")[1:3])
                m3u8data += m3u8_url + "\n"
            m3u8data += "\n#EXT-X-ENDLIST"
            c[0][7] = m3u8data
            video = c[0]
            self.save_m3u8(video)
        else:
            video = video_lists[0]
            self.save_m3u8(video)


if __name__ == '__main__':
    cookie = ''
    youku = YouKu(cookie)
    youku.start("XNjE0OTU0NDU0NA==")
