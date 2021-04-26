import mmap
import sys
import re
import os
import csv

result = None

filename = f"/test_output/{'cubic' if sys.argv[1] == 'cubic' else 'test_p_77'}/experiment_{sys.argv[1]}_output.txt"
textfile = open(os.getcwd()+filename, 'r')
filetext = textfile.read()
textfile.close()
matches = re.findall("\d* KBytes/sec", filetext)

print(matches)

with open(os.getcwd()+f"/{'cubic' if sys.argv[1] == 'cubic' else 'test_p_77'}_output.csv", mode='w') as csv_file:
    field_names = ["time", "bitrate"]
    writer = csv.DictWriter(csv_file, fieldnames=field_names)
    writer.writeheader()
    for i, el in enumerate(matches):
        writer.writerow({'time': i, 'bitrate': re.match("\d*",el).group(0)})