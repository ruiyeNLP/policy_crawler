# Privacy Policy Crawler for my current project

# About the project
This my most recent project which is based on 
[this](https://github.com/rmjacobson/privacy-crawler-parser-tokenizer). 

The functions added or modified by me will be shown as @Rui. 


# Running the Project
Please read the Virtual Environments section before trying to run this
project to save headaches.

The top-level scripts for this project's main components (crawler.py) 
can be run very simply, as shown in the example below.  
```
python src/crawler.py -n 5 data/inputs/policylink_uk.json data/inputs/ground_truth_html/ data/inputs/dictionary.txt 0.6 3 data/crawler_output/html/ data/crawler_output/stripped_text/
```


# Virtual Environments
To set up your virtual environment, refer to
[this](https://docs.python-guide.org/dev/virtualenvs/#lower-level-virtualenv)
documentation.

To download all dependencies:
```
$ pip3 install -r requirements.txt
```
