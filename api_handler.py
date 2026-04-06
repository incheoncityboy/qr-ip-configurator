import requests
from requests.auth import HTTPDigestAuth
import os

class CameraAPI:
    @staticmethod
    def set_ip_secure(current_ip, mac, new_ip, gateway="192.168.1.1", netmask="255.255.255.0", username="admin", password="password"):
        try:
            # ARP 바인딩 (이제 굳이 로그에 안 찍고 조용히 처리합니다)
            os.system(f"arp -d {current_ip} >nul 2>&1")
            formatted_mac = mac.replace(':', '-')
            os.system(f"arp -s {current_ip} {formatted_mac}")
        except:
            pass 

        url = f"http://{current_ip}/cgi-bin/update_save.cgi"
        payload = {
            'category': 'net_interface', 'nettype': '1', 
            'ipaddr': new_ip, 'netmask': netmask, 'gateway': gateway,
            'dns': '8.8.8.8', 'speed': '0', 'use_zeroconf': '1'
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest'
        }

        try:
            auth = HTTPDigestAuth(username, password)
            response = requests.post(url, data=payload, headers=headers, auth=auth, timeout=10)
            os.system(f"arp -d {current_ip} >nul 2>&1")

            resp_lower = response.text.strip().lower()
            if any(keyword in resp_lower for keyword in ["success", "updated", "ok"]) or "<table border='0'" in resp_lower:
                return True, "적용 성공"
            else:
                return False, f"실패 (HTTP {response.status_code})"
                
        except Exception as e:
            os.system(f"arp -d {current_ip} >nul 2>&1")
            return False, "접속 불가 (통신 에러)"