from flask import make_response, request

from app.crawler import bp
from app.crawler import org_crawler

@bp.route('/crawler/<path:url>')
def crawl(url):
    if not url.startswith('http://') and not url.startswith('https://'):
        full_url = "http://" + url
    else:
        full_url = url
    #return f"Retrieved URL: {full_url}"
    return org_crawler.run_report(full_url)