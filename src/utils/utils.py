#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Fri May 28 09:48:52 2021

@author: yerui
"""

import argparse, os, requests
import pickle, psutil, logging
from urllib3.exceptions import NewConnectionError
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from time import sleep
from selenium.webdriver.support import ui
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import traceback

class VerifyJsonExtension(argparse.Action):
    """
    Checks the input file that it is actually a file with
    the .json extension.  Doesn't check to see if the file contains
    json content, but was the best we could do for the time being.
    https://stackoverflow.com/a/15203955
    """
    def __call__(self,parser,namespace,fname,option_string=None):
        file = os.path.isfile(fname)
        json = fname.endswith(".json")
        if file and json:
            setattr(namespace,self.dest,fname)
        else:
            parser.error("File doesn't end with '.json'")

def print_progress_bar (iteration, total, prefix = "", suffix = "", decimals = 1, length = 100, fill = "█", printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    https://stackoverflow.com/a/34325723
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + "-" * (length - filledLength)
    print("\r%s |%s| %s%% %s" % (prefix, bar, percent, suffix), end = printEnd)
    if iteration == total:  # Print New Line on Complete
        print()

def mkdir_clean(dir_path):
    """
    Given the name of the directory, create new fresh directories using this
    name. This may require deletion of all contents that previously existed in
    this directory, or creating a previously nonexistant directory.
    In:     dir_path - the name of the directory
    Out:    n/a
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    else:
        for f in os.listdir(dir_path):
            os.remove(os.path.join(dir_path, f))

def create_driver_session(session_id, executor_url):
    """
    @Rui
    Creat a driver session 
    """     
    from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver

    # Save the original function, so we can revert our patch
    org_command_execute = RemoteWebDriver.execute

    def new_command_execute(self, command, params=None):
        if command == "newSession":
            # Mock the response
            print("newSession")
            return {'success': 0, 'value': None, 'sessionId': session_id}
        else:
            print("not newSession")
            return org_command_execute(self, command, params)

    # Patch the function before creating the driver object
    RemoteWebDriver.execute = new_command_execute

    new_driver = webdriver.Remote(command_executor=executor_url, desired_capabilities={})
    new_driver.session_id = session_id

    # Replace the patched function with original function
    RemoteWebDriver.execute = org_command_execute
    

    return new_driver

class myfox():
    """
    @Rui
    This is a class to manage the Selenium browser. Existing browser session is reused. 
    """ 
    def __init__(self):
        self.file=r'myenv/lib/python3.7/site-packages/selenium/webdriver/firefox/params.data'
        self.gecko=r'exemyenv/bin/geckodriver'

    def creatfirefox(self):
        """
        Instatiate a selenium Firefox webdriver, return it.
        """
        options = Options()
        options.binary_location = r"myenv/bin/firefox/firefox"
        options.add_argument("--headless")  
        
        profile = webdriver.FirefoxProfile()
        profile.set_preference('intl.accept_languages', 'en-GB')
        # do not load un-wanted images or cache 
        profile.set_preference("permissions.default.image", 2)
        profile.set_preference("network.http.use-cache", False)
        profile.set_preference("browser.cache.memory.enable", False)
        profile.set_preference("browser.cache.disk.enable", False)
        profile.set_preference("browser.sessionhistory.max_total_viewers", 3)
        profile.set_preference("network.dns.disableIPv6", True)
        profile.set_preference("Content.notify.interval", 750000)
        profile.set_preference("content.notify.backoffcount", 3)
        profile.set_preference("network.http.proxy.pipelining", True)
        profile.set_preference("network.http.pipelining.maxrequests", 32)
        
        driver = webdriver.Firefox(options=options, firefox_profile=profile, executable_path="myenv/bin/geckodriver") 

        params={}
        params["session_id"] = driver.session_id
        params["server_url"] = driver.command_executor._url
        
        # save the current session id and url
        with open(self.file,'wb') as f:
            pickle.dump(params, f)
        return driver

    def work(self):
        """
        Check whether geckodriver is running or not. 
        If it is runnning, try to use the current session. 
        If trior fails, delete the running geckodriver, and start a now selenium Firefox webdriver 
        If the geckodriver isn't running, creat a now selenium Firefox webdriver.         
        """
        p_name = [psutil.Process(i).name() for i in psutil.pids()]#check all running process
        if 'geckodriver' not in p_name:
            print("creat firefox")
            driver=self.creatfirefox()
        else:
            try: 
                with open(self.file, 'rb') as f:
                    params = pickle.load(f)
                driver = create_driver_session(params["session_id"], params["server_url"])
                
            except Exception as e:
                logging.error('browser does not match with geckodriver！！\n%s'% e)
                [p.kill() for p in psutil.process_iter() if p.name() == 'geckodriver.exe']
                driver = self.creatfirefox()
        return driver

def selenium_get(url):
    """
    @Rui
    requests library failed, so instantiate a full selenium web browser
    
    In:     destination of http request           
    Out:    requests_res - content of the request 
            all_links - all links found on the destination webpage. 
    """    
    #try to restart selenium after error     
    requests_res = ""
    all_links = []
    
    try: 
        driver = myfox().work()
        driver.get(url)
        # execute script to scroll down the page
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);var lenOfPage=document.body.scrollHeight;return lenOfPage;")
        # sleep for 10s
        sleep(10)
        
        requests_res = driver.page_source
        
        urls = ui.WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "a")))
        all_links = [url.get_attribute("href") for url in urls]

    except Exception as e:
        sleep(2)
        print (traceback.format_exc())
    finally:
        sleep(2)
        driver.refresh()
        
        if requests_res == "":
            print("\tselenium failed for " + url + " -> failed")
        else:
            print("\tselenium SUCCESS! for " + url)
            
        return requests_res, all_links

def request(url):
    """
    @Rui
    Makes a simple HTTP request to the specified url and returns its
    contents. If it fails, make a selenium request instead.
    
    In:     destination of http request           
    Out:    requests_res - content of the request 
            all_links - with selenium request, return all links on the destination
                        webpage. If it is the HTTP request, return []. 
    """
    from verification.verify import strip_text
    requests_res = ""
    all_links = []
    exceptions = (requests.exceptions.ReadTimeout,
                  requests.exceptions.ConnectTimeout,
                  requests.ConnectionError,
                  requests.ConnectTimeout,
                  ConnectionError,
                  ConnectionAbortedError,
                  ConnectionResetError)
    try:
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:73.0) Gecko/20100101 Firefox/73.0"
        user_agent = "Mozilla/5.0 (X11; Linux x86_64; rv:29.1) Gecko/20100101 Firefox/88.0"
        accept = "*/*"
        accept_language = "en-US,en;q=0.5"
        accept_encoding = "gzip, deflate"
        dnt = "1"
        up_insecure_reqs = "1"
        headers = {
            "User-Agent": user_agent,
            "Upgrade-Insecure-Requests": up_insecure_reqs,
            "DNT": dnt,"Accept": accept,
            "Accept-Language": accept_language,
            "Accept-Encoding": accept_encoding
        }        
        requests_res = requests.get(url, headers=headers, timeout=(3,6))
        requests_res = requests_res.text
        
        if not requests_res or not strip_text(requests_res):
            print("requests failed for " + url + " -> trying selenium")
            requests_res, all_links = selenium_get(url)

    except requests.exceptions.ConnectionError as e:
        print("REQUESTS connection refused for " + url)
    except (exceptions) as e:
        print("REQUEST PROBLEM: " + str(e))
        return ""
    except Exception as e:
        print("UNKNOWN PROBLEM: " + str(e))

    return requests_res, all_links