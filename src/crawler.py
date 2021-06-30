"""
Privacy Policy Project
Web Crawler
Takes in list of Amazon Alexa Top N sites, visits them and tries to
discover the link to and download the Privacy Policy HTML page for
that site.  Also attempts to visit links contained within the policies
to discover relevant linked content.  Outputs directory of HTML docs
containing privacy policies and a txt file containing an audit trail
of links visited and decisions about those policies.
"""

import argparse, datetime, json, matplotlib, os, pandas as pd, re, signal, sys
from bs4 import BeautifulSoup
from multiprocessing import Pool, Value, cpu_count, current_process, Manager
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from utils.utils_reuse import print_progress_bar, request, get_driver, VerifyJsonExtension, myfox
from verification.verify import get_ground_truth, is_duplicate_policy, is_english, mkdir_clean, strip_text, is_same_webpage




class DomainLink():
    def __init__(self, link, sim_score, html_outfile, stripped_outfile, access_success, valid, duplicate):
        self.link = link
        self.sim_score = sim_score
        self.html_outfile = html_outfile
        self.stripped_outfile = stripped_outfile
        self.access_success = access_success
        self.valid = valid
        self.duplicate = duplicate

class CrawlReturn():
    def __init__(self, domain, access_success, policy_ground_truth):
        self.domain = domain
        self.sim_avg = 0.0
        self.link_list = []
        self.access_success = access_success
        self.policy_ground_truth = policy_ground_truth
        self.find_true_policy = None
    def add_link(self, link, sim_score, html_outfile, stripped_outfile, access_success, valid, duplicate):
        link = DomainLink(link, sim_score, html_outfile, stripped_outfile, access_success, valid, duplicate)
        self.link_list.append(link)
        self.sim_avg = self.sim_avg + ((sim_score-self.sim_avg)/len(self.link_list))

def find_keywords(country):
    if country == 'uk':
        return ["privacy", "help", "policy", "policies"]
    else:
        return ["privacy","gdpr","data policy","privacy policy", "cookie policy"]
    
def verify(html_contents, ground_truth):
    """
    This function will verify that the HTML we scraped is actually a privacy
    policy.  (For example, we need to reject HTML which turns out to be an
    article about privacy or a pointer to policies as opposed to a privacy policy.)
    We accomplish this by comparing against a ground truth.  We build our ground
    truth by constructing a bag of words from human-verified privacy policies.
    HTML which does not pass the verification process will be logged then
    deleted.
    In:     html_contents (aka stripped html text)
    Out:    cosine similarity score of ground truth and policy document
    """
    # verify majority of the contents are english-language, discard if not
    if not is_english(dictionary, html_contents):
        return 0
    
    # Create the Document Term Matrix and pandas dataframe
    # https://www.machinelearningplus.com/nlp/cosine-similarity/
    documents = [ground_truth, html_contents]
    count_vectorizer = TfidfVectorizer()
    sparse_matrix = count_vectorizer.fit_transform(documents)
    doc_term_matrix = sparse_matrix.todense()
    df = pd.DataFrame(doc_term_matrix, 
            columns=count_vectorizer.get_feature_names(),
            index=["ground_truth", "corp"])

    sim_score = cosine_similarity(df, df)

    return sim_score[0,1]

def clean_link(link):
    """
    Many links will direct you to a specific subheading of the page, or
    reference some particular component on the page.  We don't want to
    consider these "different" URLs, so parse this out.
    In:     string representiaton of a URL link.
    Out:    "cleaned" version of the link parameter.
    """
    link = link.split("#", 1)[0]
                      
    return link

def find_policy_links(full_url, html, current_links):
    """
    @Rui
    Find all the links on the page.  Only returns links which contain some case
    permutation of the PRIVACY_POLICY_KEYWORDS.  Exact duplicate links removed
    before return, but similar links or links that lead to the same place will
    be dealt with later in the process.
    In:     full_url - A string representing the full name of the URL
            soup - BeautifulSoup4 object instantiated with the HTML of the URL
    Out:    list of all links on the page
    """
    links = []    
    index = len(full_url.split('.')) - 1
    country = full_url.split('.')[index] 
    keywords = find_keywords(country)

    for kw in keywords:        
        #html case
        if current_links == []:
            soup = BeautifulSoup(html, "html.parser")
            all_links = soup.find_all("a")
            #print("all_links in find_policy_links", len(all_links))
            for link in all_links:
                if "href" in link.attrs:
                    #print(link.string, link["href"])
                    if (kw in str(link.string).lower()) or (kw in str(link["href"]).lower()):
                        final_link = link["href"]
                        #print("final_link", final_link)

                        if final_link in link_dict:
                            link_dict[final_link] += 1
                        # print("Already visited this link -> skipping")
                            continue    # we've already visited this link, skip this whole thing
                        else:
                            link_dict[final_link] = 0

                        # Not a proper link; to-do change later
                        if "javascript" in final_link.lower(): continue
                        if len(final_link) < 3: continue
                        if "mailto:" in final_link.lower(): continue

                        # This link is complete, add it to our list
                        if "http" in final_link:
                        # links.append(final_link)
                            links.append(clean_link(final_link))
                            continue

                    # This link is incomplete. Complete it.
                        if final_link[0] != "/":
                            final_link = full_url + "/" + final_link
                        elif final_link[:2] == "//":
                            final_link = "http://" + final_link[2:]
                        else:
                            final_link = full_url + final_link
                    # links.append(final_link)
                        links.append(clean_link(final_link))
                #print(links)
        else:
            all_links = current_links
            for i in range(len(all_links)):
                #print(all_links[i])
                if (kw in str(all_links[i])):
                    
                    final_link = all_links[i]

                    if final_link in link_dict:
                        link_dict[final_link] += 1
                        # print("Already visited this link -> skipping")
                        continue    # we've already visited this link, skip this whole thing
                    else:
                        link_dict[final_link] = 0

                        # Not a proper link
                    if "javascript" in final_link.lower(): continue
                    if len(final_link) < 3: continue
                    if "mailto:" in final_link.lower(): continue

                        # This link is complete, add it to our list
                    if "http" in final_link:
                        # links.append(final_link)
                        links.append(clean_link(final_link))
                        continue

                    # This link is incomplete. Complete it.
                    if final_link[0] != "/":
                        final_link = full_url + "/" + final_link
                    elif final_link[:2] == "//":
                        final_link = "http://" + final_link[2:]
                    else:
                        final_link = full_url + final_link
                    # links.append(final_link)
                    links.append(clean_link(final_link))            

    links = list(dict.fromkeys(links))  # remove obvious duplicates
        
    return links

def crawl(domain_zip):

    """
    @Rui
    Primary function for the process pool.
    Crawl websites for links to privacy policies.  First check if
    the website can be reached at all, then find list of policy links
    on first page.  Then loop through links to see if the links are 
    valid policies.  Keep statistics in every subprocess for summary
    at end.
    
    In:     domain_zip[0] - domain landing page string
            domain_zip[1] - true links to the privacy policy of the domain
    Out:    CrawlReturn obj containing links, statistics about links,
            output files, etc.
    """
    domain = domain_zip[0]
    domain_policy = domain_zip[1]

    half_full_url = domain if ("www." in domain) else "www." + domain
    full_url = half_full_url if ("https" in half_full_url) else "https://" + half_full_url
    domain_html, all_links = request(full_url)

    if strip_text(domain_html) == "" and domain_html =="" and all_links ==[]:
        full_url = domain if ("http" in domain) else  "http://" + domain        
        domain_html, all_links = request(full_url)
        if strip_text(domain_html) == "" and domain_html =="" and all_links ==[]:
            full_url = domain if ("https" in domain) else  "https://" + domain
            domain_html, all_links = request(full_url)
            if strip_text(domain_html) == "" and domain_html =="" and all_links ==[]:
                failed_access_domain = CrawlReturn(domain, False, domain_policy)
                with index.get_lock():  # Update progress bar
                    print("failed to access domain: ", full_url)
                    index.value += 1
                    print_progress_bar(index.value, len(domain_list), prefix = "Crawling Progress:", suffix = "Complete", length = 50)
                return failed_access_domain

    # get links from domain landing page, return if none found
    links = find_policy_links(full_url, domain_html, all_links)
    
    # no link case 
    if len(links) == 0:
        no_link_domain = CrawlReturn(domain, True, domain_policy)
        no_link_domains.append(no_link_domain.domain)
        with index.get_lock():  # Update progress bar
            index.value += 1
            print_progress_bar(index.value, len(domain_list), prefix = "Crawling Progress:", suffix = "Complete", length = 50)
        return no_link_domain

    # go down the link rabbit hole to download the html and verify that they are policies
    retobj = CrawlReturn(domain, True, domain_policy)
    domain_successful_links = []
    domain_failed_links = []
    depth_count = 0
    output_count = 0
    for link in links:
        # link_html = request(link, driver)
        link_html, link_all_links = request(link)
        link_contents = strip_text(link_html) #to-do: check whether it works for selenium cases
 
        if link_contents == "":
            domain_failed_links.append(link)
            retobj.add_link(link, 0.0, "N/A", "N/A", False, False, False)
            continue    # policy is empty, skip this whole thing
        
        # add links on this page to the list to be visited if they are new
        if depth_count < max_crawler_depth:
            depth_count += 1
            new_links = find_policy_links(full_url, link_html, link_all_links)
            for l in new_links:
                if l not in links:
                    links.append(l)

        # get similarity score, check against the score threshold to see if policy
        sim_score = verify(link_contents, ground_truth)
        is_policy = sim_score >= cos_sim_threshold
        #print(link_html)

        # if this page is a policy, check duplicate then write out to file
        if is_policy:
            if is_duplicate_policy(link_contents, domain, policy_dict):
                retobj.add_link(link, 0.0, "N/A", "N/A", True, True, True)
                continue    # we've already seen this policy, skip
            domain_successful_links.append(link)
            output_count += 1
            html_outfile = html_outfolder + domain[:-4] + "_" + str(output_count) + ".html"
            with open(html_outfile, "a") as fp:
                fp.write(link_html)
            stripped_outfile = stripped_outfolder + domain[:-4] + "_" + str(output_count) + ".txt"
            with open(stripped_outfile, "a") as fp:
                fp.write(link_contents)
            retobj.add_link(link, sim_score, html_outfile, stripped_outfile, True, True, False)
        
        # this isn't a policy, so just add it to the stats and continue
        else:
            if is_duplicate_policy(link_contents, domain, policy_dict):
                retobj.add_link(link, 0.0, "N/A", "N/A", True, False, True)
                continue    # we've already seen this policy, skip
            domain_failed_links.append(link)
            retobj.add_link(link, sim_score, "N/A", "N/A", True, False, False)
    
    if sum(link.valid == True for link in retobj.link_list) == 0:
        failed_link_domains.append(retobj.domain)
    else:
        successful_domains.append(retobj)
        if retobj.policy_ground_truth == None:
        
    with index.get_lock():  # Update progress bar
        index.value += 1
        print_progress_bar(index.value, len(domain_list), prefix = "Crawling Progress:", suffix = "Complete", length = 50)
    
    return retobj

def produce_summary(all_links):
    """
    @Rui
    Produce string output for the summary file in the format of:
    domain.com (avg sim score = 0.XX)
    => (link message) https://www.domain.com/path/to/policy.html
    In:     list CrawlerReturn objects containing links and statistics
    Out:    string representation to be written out to file.
    """
    timestamp = "_{0:%Y%m%d-%H%M%S}".format(datetime.datetime.now())
    summary_string = "Summary of Crawler Output (" + timestamp + ")\n"
    
    for domain in all_links:
        max_sim_score = 0
        policy_link = ""
        if not domain.access_success:
            failed_access_domains.append(domain.domain)
            continue;
        if not domain.access_success:
            summary_string += (domain.domain + " -- NO_ACCESS\n\n")
        if domain.access_success and len(domain.link_list) == 0:
            summary_string += (domain.domain + " -- NO_LINKS\n\n")
        else:
            sim_avg = str(round(domain.sim_avg, 2))
            summary_string += (domain.domain + " (avg sim = " + sim_avg + ")" + "\n")
            for link in domain.link_list:
                max_sim_score = 0
                policy_link = ""
                sim_score = str(round(link.sim_score, 2))
                if link.access_success == False:
                    summary_string += ("=> (NO_ACCESS) " + link.link + " -> ")
                elif link.duplicate == True:
                    summary_string += ("=> (DUPLICATE) " + link.link + " -> ")
                else:
                    summary_string += ("=> (" + sim_score + ") " + link.link + " -> ")
                    if round(link.sim_score, 2) > max_sim_score and domain.domain in link.link:
                        max_sim_score = round(link.sim_score, 2)
                        policy_link = link.link
                summary_string += (link.html_outfile + " & " + link.stripped_outfile + "\n")
            summary_string += ("=> (" + "privacy policy" + ") " + policy_link)
            summary_string += "\n"
        print(domain.domain, policy_link, max_sim_score)
        if domain.policy_ground_truth != None:
            if policy_link == domain.policy_ground_truth:
                domain.find_true_policy = True
                find_true_policy_domains.append(domain.domain)
            elif is_same_webpage(policy_link, domain.policy_ground_truth):
                domain.find_true_policy = True
                find_true_policy_domains.append(domain.domain)

    summary_string += "   # of Successful Domains = " + str(len(successful_domains)) + " (" + str(round(len(successful_domains)/len(domain_list)*100, 2)) + "%).\n"
    summary_string += "   Could not access " + str(len(failed_access_domains)) + " (" + str(round(len(failed_access_domains)/len(domain_list)*100, 2)) + "%) domains.\n"
    summary_string += "   No links found for " + str(len(no_link_domains)) + " (" + str(round(len(no_link_domains)/len(domain_list)*100, 2)) + "%) domains.\n"
    summary_string += "   No valid links found for " + str(len(failed_link_domains)) + " (" + str(round(len(failed_link_domains)/len(domain_list)*100, 2)) + "%) domains.\n"
    summary_string += "   # of true policy domains = " + str(len(find_true_policy_domains)) + ".\n"
    summary_string += "\n"    
    
    return summary_string

def start_process(i):
    """
    Set inter-process shared values to global so they can be accessed.
    Ignore SIGINT in child workers, will be handled to enable restart.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)

if __name__ == '__main__':
    """
    @Rui
    """    
    argparse = argparse.ArgumentParser(description="Crawls provided domains to gather privacy policy html files.")
    argparse.add_argument(  "-n", "--num_domains",
                            type=int,
                            default=-1,
                            required=False,
                            help="number of domains to crawl.  If blank, set to entire input list.")
    argparse.add_argument(  "domain_list_file",
                            help="json file containing list of top N sites to visit.",                       
                            action=VerifyJsonExtension)
    argparse.add_argument(  "ground_truth_html_dir",
                            help="directory containing html files of verification ground truth vector.")
    argparse.add_argument(  "dictionary",
                            help="txt file containing english-language dictionary.")
    argparse.add_argument(  "cos_sim_threshold",
                            type=float,
                            help="minimum cosine similarity between html contents and ground truth vector to be considered a policy.")
    argparse.add_argument(  "max_crawler_depth",
                            type = int,
                            help="number of layers to repeat find_policy_links for each domain.")
    argparse.add_argument(  "html_outfolder",
                            help="directory to dump HTML output of crawler.")
    argparse.add_argument(  "stripped_outfolder",
                            help="directory to dump stripped text output of crawler.")
    args = argparse.parse_args()
    domain_list_file = args.domain_list_file
    ground_truth_html_dir = args.ground_truth_html_dir
    dictionary = args.dictionary
    cos_sim_threshold = args.cos_sim_threshold
    max_crawler_depth = args.max_crawler_depth
    html_outfolder = args.html_outfolder
    stripped_outfolder = args.stripped_outfolder
    mkdir_clean(html_outfolder)
    mkdir_clean(stripped_outfolder)
    summary_outfile = args.html_outfolder + "../summary.txt"
    sys.setrecursionlimit(10**6)

    # get domain list, domain policy url and verification ground truth
    with open(domain_list_file, "r") as fp:
        domain_file = json.load(fp)
        domain_policy = list(domain_file['PrivacyPolicy_English_footer'].values())
        domain_list = list(domain_file['SiteName'].values())
    if args.num_domains != -1:
        domain_list = domain_list[:args.num_domains]
        
    ground_truth = get_ground_truth(ground_truth_html_dir)

    # set up shared resources for subprocesses
    index = Value("i",0)        # shared val, index of current crawled domain
    shared_manager = Manager()    # manages lists shared among child processes
    successful_domains = shared_manager.list()       # at least one link in each domain is a valid policy
    no_link_domains = shared_manager.list()          # domains with no links
    failed_link_domains = shared_manager.list()      # domains with no valid links
    failed_access_domains = shared_manager.list()    # domains where the initial access failed
    find_true_policy_domains = shared_manager.list() # domains that find the correct link to privacy policy
    policy_dict = shared_manager.dict()              # hashmap of all texts to quickly detect duplicates
    link_dict = shared_manager.dict()                # hashmap of all links to detect duplicates without visiting them

    pool_size = cpu_count() - 1   
    pool = Pool(
        processes=pool_size,
        initializer=start_process,
        initargs=[index]
    )
    
    driver=myfox().creatfirefox() # Instatiate a selenium Firefox webdriver 
    
    all_links = pool.map(crawl, list(zip(domain_list, domain_policy)))    # map keeps domain_list order

    pool.close()  # no more tasks
    pool.join()   # merge all child processes   
    driver.quit() 
    
    # produce summary output files
    print("Generating summary information...")
    
    # add some evaluation and summary on the privacy policy result 
    with open(summary_outfile, "w") as fp:
        fp.write(produce_summary(all_links))
        
    print("Done")

    