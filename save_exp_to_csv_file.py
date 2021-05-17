import mmap
import sys
import re
import os
import csv
import glob

"""
Parsing output of experiments and saving them to csv files
"""

class ExperimentHandler:
    def __init__(self, input_directory: str, output_directory: str):
        self.input_directory = input_directory
        self.output_directory = output_directory
        # get names of experiments
        dirlist = glob.glob(os.getcwd()+f"/{input_directory}/*")
        experiments = []
        self.e_to_avb={}
        for _dir in dirlist:
            experiment_name = re.findall("[a-zA-Z0-9_]*$", _dir)
            if (experiment_name[0] != "weibull_threads" and 
                experiment_name[0] != "result" and experiment_name!="csv_files" and 
                experiment_name[0] != "graphs"):
                experiments.append(experiment_name[0])
        self.experiments = experiments
        print("create output dir")
        try: 
            os.mkdir(os.getcwd()+f"/{output_directory}")
        except:
            print("dir already created")

    def prepare_pre_final_result(self, experiment) -> None:
        # print(f"Prepare pre final results for {experiment}")
        try: 
            input_filename = f"{self.input_directory}/{experiment}/{experiment}_iperf.txt"
            textfile = open(os.getcwd()+f"/{input_filename}", 'r')
            filetext = textfile.read()
            textfile.close()
            el = re.findall("Interval\s*Transfer\s*Bitrate\s*Retr\s*\n.*[0-9,\.]+\s*KBytes/sec", filetext)[0]
            average_bitrate = re.findall("[0-9,\.]+", re.findall("[0-9,\.]+ KBytes/sec", el)[0])[0]
            self.e_to_avb[experiment] = average_bitrate
        except Exception as e:
            print (f"Exception in prepare pre final res: {e}")
            print(experiment)

    def save_pre_final_result(self) -> None:
        print("Save pre final res")
        try: 
            os.mkdir(os.getcwd()+f"/{self.input_directory}/result")
        except:
            pass
        output_filename = f"{self.input_directory}/result/preparing.csv"
        with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
            field_names = ["experiment", "average_bitrate"]
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            for e, avb in self.e_to_avb.items():
                writer.writerow({'experiment': e, 'average_bitrate': avb})

    # def save_final_result(self) -> None:
    #     input_filename = f"{self.input_directory}/result/preparing.csv"
    #     output_filename = f"{self.input_directory}/result/final.csv"
    #     exp_result = {}
    #     tr = ["cubic", "bbr", "bic", "htcp", "highspeed", "illinoise"]
    #     traditional_exp = {}.fromkeys(tr, 0.0)
    #     trt = [e + "_t" for e in tr]

    #     with open(os.getcwd()+ f"/{input_filename}", mode='r') as csv_file:
    #         reader = csv.DictReader(csv_file)
    #         for line in reader:
    #             is_traditional = False
    #             for t in tr:
    #                 if t in line["experiment"]:
    #                     traditional_exp[line["experiment"]] = int(line["average_bitrate"])
    #                     is_traditional = True
    #                     break
    #             if not is_traditional:
    #                 exp_result[line["experiment"]] = int(line["average_bitrate"])  
    #     better_than = {}.fromkeys(["better_than_" + e for e in traditional_exp],"")

    #     with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
    #         field_names = ["experiment", "res", *tr,  *better_than]
    #         writer = csv.DictWriter(csv_file, fieldnames=field_names)
    #         writer.writeheader()
    #         for e, av_speed in exp_result.items():
    #             for b,t in zip(better_than.keys(), traditional_exp.keys()):
    #                 better_than[b] = 'yes' if av_speed >= traditional_exp[t] else 'no'
    #             writer.writerow({'experiment': e, 'res': av_speed, **traditional_exp, **better_than})


    def saving_results_from_iperf(self, experiment) -> None:
        input_filename = f"{self.input_directory}/{experiment}/{experiment}_iperf.txt"
        output_filename = f"{self.output_directory}/{experiment}/{experiment}_iperf.csv"

        textfile = open(os.getcwd()+f"/{input_filename}", 'r')
        filetext = textfile.read()
        textfile.close()
        matches = re.findall("\d* KBytes/sec\s+\d*\s+[0-9,\.]+\s+(?:KBytes|MBytes)", filetext)

        with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
            field_names = ["time", "bitrate", "cwnd"]
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            for i, el in enumerate(matches):
                bitrate_and_cwnd = re.findall("[0-9,\.]+", el) #first will be bitrate, last is cwnd
                if bitrate_and_cwnd[-1].find('.') != -1:
                    if len(re.findall("MBytes", el)) != 0:
                        bitrate_and_cwnd[-1] = float(bitrate_and_cwnd[-1])*1000
                writer.writerow({'time': i, 'bitrate': bitrate_and_cwnd[0], 'cwnd': bitrate_and_cwnd[-1]})

    def saving_results_from_dmesg(self, experiment) -> None:
        input_filename = f"{self.input_directory}/{experiment}/{experiment}_dmesg.txt"
        output_filename = f"{self.output_directory}/{experiment}/{experiment}_dmesg.csv"

        textfile = open(os.getcwd()+f"/{input_filename}", 'r')
        filetext = textfile.read()
        textfile.close()
        matches = re.findall(".*\d\d:\d\d:\d\d.*UPDATE cwnd = \d*", filetext)
        matches = [{"time": re.findall("\d\d:\d\d:\d\d", el)[0], "cwnd": re.findall("\d+", re.findall("= \d+", el)[0])[0], "speed": "?", "forecast": "?"} for el in matches]
        speed_matches = re.findall(".*\d\d:\d\d:\d\d.*buffer_speed_last = \d+.*forecast = \d+", filetext)
        speed_matches = [{"time": re.findall("\d\d:\d\d:\d\d", el)[0], "cwnd": "?", "speed": re.findall("\d+", re.findall("buffer_speed_last = \d+", el)[0])[0], "forecast": re.findall("\d+", re.findall("forecast = \d+", el)[0])[0]} for el in speed_matches]
        all_matches = matches + speed_matches
        all_matches = sorted(all_matches, key=lambda tcs: tcs['time']) #sort by id of log, not by time

        with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
            field_names = ["time", "CWND", "speed", "forecast"]
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            last_speed = 0
            last_forecast = 0
            last_cwnd = 0
            for el in all_matches:
                last_speed = el['speed'] if el['speed'] != "?" else last_speed
                last_forecast = el['forecast'] if el['forecast'] != "?" else last_forecast
                last_cwnd = el['cwnd'] if el['cwnd'] != "?" else last_cwnd
                last_time = el['time']
                writer.writerow({'time': last_time, 'CWND': last_cwnd, 'speed': last_speed, 'forecast': last_forecast})

            


if __name__ == '__main__':
    experiment_handler = ExperimentHandler(input_directory="test_output", output_directory="test_output/csv_files")
    for experiment in experiment_handler.experiments:
        os.mkdir(os.getcwd()+f"/{experiment_handler.output_directory}/{experiment}")
        experiment_handler.saving_results_from_iperf(experiment)
        experiment_handler.prepare_pre_final_result(experiment)
        experiment_handler.saving_results_from_dmesg(experiment)
        # experiment_handler.forecast_results_from_dmesg(experiment)
    experiment_handler.save_pre_final_result()
    # experiment_handler.save_final_result()
