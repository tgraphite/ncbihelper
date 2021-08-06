import re

f = open('check.html', 'r')
text = f.read()
rid_regex = '(WAITING)|(UNKNOWN)|(READY)'
rid = re.search(pattern=rid_regex, string=text).group()
print(rid)