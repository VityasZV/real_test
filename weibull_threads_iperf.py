import subprocess
import os
import sched, time
import scipy
from scipy.stats import weibull_min
import functools

iperf_clients = []
def iperf(server, port):
    iperf_clients.append(subprocess.Popen(["ip", "netns", "exec", "ns_client", "iperf3", "-c", "192.168.1.1", "-B", "192.168.1.2", "-p", f"{port}", "-f", "K", "-t", "10", "-C", "cubic"]))
    # subprocess.Popen(["ip", "netns", "exec", "ns_client", "iperf3", "-c", "192.168.1.1", "-B", "192.168.1.2", "-p", f"{port}", "-f", "K", "-t", "5", "-C", "cubic",
    #                   ">", f"testoutput/weibull_threads/{os.getenv('EXPERIMENT')}.txt"])
    # subprocess.Popen(f"ip netns exec ns_client iperf3 -c 192.168.1.1 -B 192.168.1.2 -p {port} -f K -t 5 -C cubic > test_output/weibull_threads/{os.getenv('EXPERIMENT')}.txt")

k = 2.4

x = weibull_min.rvs(k, loc=2, scale=10, size=10)
x = [round(e) for e in x]
x = sorted(x)
print(f"{x} HERE IS X")


try:
    print("create dir for weibull logs")
    os.mkdir(os.getcwd()+f"/test_output/weibull_threads")
except Exception:
    pass


# Set up scheduler
print("Set up scheduler")
sch = sched.scheduler(time.time, time.sleep)

# Set up iperf servers:
print("Set up iperf servers")
servers = []
start_port = 5400
for el in x:
    servers.append([subprocess.Popen(["ip", "netns", "exec", "ns_server", "iperf3","-s","-p",f"{start_port}","-f", "K", "&"]), start_port])
    start_port+=1

# Block until the action has been run
start_time = time.time()
for i in range(len(x)): 
    # Schedule when we want the iperf action to occur
    print(f"TIME OF RUNNING: {start_time+x[i]}, {time.time()}")
    sch.enterabs(start_time+x[i], 0, functools.partial(iperf, servers[i][0], servers[i][1]))
sch.run()

print("wait clients")
time.sleep(11)
# for client in iperf_clients:
#     subprocess.run(f"wait {client.pid}", shell=True)

#kill servers
print("KILL SERVERS")
for s in servers:
    subprocess.run(f"kill {s[0].pid}", shell=True)
