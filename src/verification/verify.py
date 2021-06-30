"""
Privacy Policy Project
verify.py
Checks every file in list of given webpages is actually a privacy
policy.  
Checks wether the text is majority english, then does 
cosine similarity from ground truth using TfidfVectorizer.
Currently seems like ~60% is the cutoff.
"""

import os 
import re
from bs4 import BeautifulSoup
from utils.utils import request

def load_dictionary(dictionary):
    dictionaryFile = open(dictionary)
    ENGLISH_WORDS = {}
    for word in dictionaryFile.read().split("\n"):
        ENGLISH_WORDS[word] = None
        dictionaryFile.close()
    return ENGLISH_WORDS

def get_english_count(dictionary, html_contents):
    ENGLISH_WORDS = load_dictionary(dictionary)
    html_contents = html_contents.upper()
    html_contents = remove_nonletters(html_contents)
    possibleWords = html_contents.split()
    if possibleWords == []:
        return 0.0 # no words at all, so return 0.0
    matches = 0
    for word in possibleWords:
        if word in ENGLISH_WORDS:
            matches += 1
    return float(matches) / len(possibleWords)

def remove_nonletters(html_contents):
    UPPERLETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    LETTERS_AND_SPACE = UPPERLETTERS + UPPERLETTERS.lower() + " \t\n"
    lettersOnly = []
    for symbol in html_contents:
        if symbol in LETTERS_AND_SPACE:
            lettersOnly.append(symbol)
    return "".join(lettersOnly)

def is_english(dictionary, html_contents, wordPercentage=50, charPercentage=85):
    """
    By default, 50% of the words in the document should be in the english 
    dictionary, and 85% of the characters should be letters rather than 
    numbers or symbols.

    In:     string representaiton of the text to be verified as english
    Out:    boolean of whether the text is mostly english
    """
    wordsMatch = get_english_count(dictionary, html_contents) * 100 >= wordPercentage
    numLetters = len(remove_nonletters(html_contents))
    if len(html_contents) == 0:
        html_contentsLettersPercentage = 0
    else:
        html_contentsLettersPercentage = float(numLetters) / len(html_contents) * 100
    lettersMatch = html_contentsLettersPercentage >= charPercentage
    return wordsMatch and lettersMatch

def remove_bad_tags(soup):
    """
    Removes script and style elements from the soup to ensure we don't
    look at these when we don't need to.

    In:     BeatifulSoup tree object.
    Out:    cleaned version of that BeatifulSoup tree object.
    """
    bad_tags = ["style", "script", "noscript", "head", "title", "meta", 
                "[document]", "img", "iframe", "header", "footer", "nav"]
    for tag in soup(bad_tags):
        tag.decompose()
    return soup

def strip_text(html):
    """
    This function takes in a html document represented as a string and
    removes all tags known to be irrelevant to the policy text, then
    returns all the visible text elements in a single string.

    In:     string containing html document bytes
    Out:    string containing text of visible policy text
    """
    if html == "":
        return ""   # return nothing if there is nothing
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        return ""   # if there's no soup, we don't care
    
    # Remove all script and style elements
    soup = remove_bad_tags(soup)
    return " ".join([text for text in soup.stripped_strings])

def remove_company_names(html_contents, name):
    """
    All policies reference their own company/organization names and
    specific service names or collaborator names that only that
    particular organization mentiions in their policy.  If these
    names are referenced often enough, they can skew similarity
    scores.  TfidfVectorizer attempts to balance this out by
    comparing word frequency with document frequency, but this
    is still a good effort to expand upon.

    In:     string representation of the extracted html contents
    Out:    string representation without specific org names
    """
    html_contents = re.sub(name, " ", html_contents, flags=re.IGNORECASE)
    return html_contents

def get_ground_truth(ground_truth_html_dir):
    """
    This function builds one massive ground truth string containing
    the relevant text of all html documents in the ground truth
    corpus.  These policies have been reviewed by a human to verify
    they contain privacy policies.  The dataset has been expanded after
    various experiments showed policies on the edge of acceptable
    cosine similarity.

    In:     n/a, ground_truth_html_dir directory set in main
    Out:    string containing text of all ground truth policy html docs
    """
    ground_truth = ""
    for policy in os.listdir(ground_truth_html_dir):
        with open(ground_truth_html_dir + policy, "rb") as fp:
            html_contents = fp.read()
        html_contents = remove_company_names(strip_text(html_contents), policy[:-5]) + " "
        ground_truth += html_contents
    return ground_truth

def is_duplicate_policy(link_contents, domain, policy_dict):
    """
    This function will compare the current policy with the
    previously verified policies to see if it is a duplicate.
    """
    if link_contents in policy_dict:
        return True
    else:
        policy_dict[link_contents] = domain
        return False

def is_same_webpage(link1, link2):
    """
    @Rui
    This function will check whether the two given urls link to
    the same webpage
    
    In:     two links or domains need to compare
    Out:    boolean of whether two urls link to the same webpage
    """       
    full_url1 = link1 if ("http" in link1) else "http://" + link1
    full_url2 = link1 if ("http" in link2) else "http://" + link2
    domain_html1, all_links1 = request(full_url1)
    domain_html2, all_links2 = request(full_url2)
    if domain_html1 == domain_html2 and domain_html1 != "":
        return True
    else:
        return False




        