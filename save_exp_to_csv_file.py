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
        print(dirlist)
        print(experiments)
        print("T")
        self.experiments = experiments
        print("create output dir")
        try: 
            os.mkdir(os.getcwd()+f"/{output_directory}")
        except:
            print("dir already created")

    def prepare_pre_final_result(self, experiment) -> None:
      
        input_filename = f"{self.input_directory}/{experiment}/{experiment}_iperf.txt"
        textfile = open(os.getcwd()+f"/{input_filename}", 'r')
        filetext = textfile.read()
        textfile.close()
        el = re.findall("Interval\s*Transfer\s*Bitrate\s*Retr\s*\n.*[0-9,\.]+\s*KBytes/sec", filetext)[0]
        average_bitrate = re.findall("[0-9,\.]+", re.findall("[0-9,\.]+ KBytes/sec", el)[0])[0]
        self.e_to_avb[experiment] = average_bitrate

    def save_pre_final_result(self) -> None:
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

    def save_final_result(self) -> None:
        input_filename = f"{self.input_directory}/result/preparing.csv"
        output_filename = f"{self.input_directory}/result/final.csv"
        exp_result = {}
        cubic = 0.0
        bbr = 0.0
        with open(os.getcwd()+ f"/{input_filename}", mode='r') as csv_file:
            reader = csv.DictReader(csv_file)
            for line in reader:
                if line["experiment"] == "cubic_t":
                    cubic = int(line["average_bitrate"])
                elif line["experiment"] == "bbr_t":
                    bbr = int(line["average_bitrate"])
                else:
                    exp_result[line["experiment"]] = int(line["average_bitrate"])
        print(exp_result)
        with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
            field_names = ["experiment", "res", "cubic", "bbr", "better_than_cubic", "better_than_bbr"]
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            for e, av_speed in exp_result.items():
                writer.writerow({'experiment': e, 'res': av_speed, "cubic": cubic, "bbr": bbr,
                                 'better_than_cubic': 'yes' if av_speed >= cubic else 'no',
                                 'better_than_bbr'  : 'yes' if av_speed >= bbr   else 'no'})


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
        output_filename_filtr = f"{self.output_directory}/{experiment}/{experiment}_dmesg_f.csv"
        output_filename_filtr_unused = f"{self.output_directory}/{experiment}/{experiment}_dmesg_f_unused.csv"

        textfile = open(os.getcwd()+f"/{input_filename}", 'r')
        filetext = textfile.read()
        print(f"SIZE OF FILETEXT dmesg {len(filetext)}")
        textfile.close()
        matches = re.findall(".*\d\d:\d\d:\d\d.*UPDATE cwnd = \d*", filetext)
        matches = [{"time": re.findall("\d\d:\d\d:\d\d", el)[0], "cwnd": re.findall("\d+", re.findall("= \d+", el)[0])[0], "speed": "?", "forecast": "?"} for el in matches]
        speed_matches = re.findall(".*\d\d:\d\d:\d\d.*buffer_speed_last = \d+.*forecast = \d+", filetext)
        speed_matches = [{"time": re.findall("\d\d:\d\d:\d\d", el)[0], "cwnd": "?", "speed": re.findall("\d+", re.findall("buffer_speed_last = \d+", el)[0])[0], "forecast": re.findall("\d+", re.findall("forecast = \d+", el)[0])[0]} for el in speed_matches]
        all_matches = matches + speed_matches
        all_matches = sorted(all_matches, key=lambda tcs: tcs['time']) #sort by id of log, not by time

        # with open(os.getcwd()+ f"/{output_filename_filtr_unused}", mode='w') as csv_file:
        #     field_names = ["time", "CWND", "estimated_speed"]
        #     writer = csv.DictWriter(csv_file, fieldnames=field_names)
        #     writer.writeheader()
        #     last_speed = ''
        #     last_cwnd = ''
        #     last_time = all_matches[0]['time']
        #     time_i = 0
        #     for el in all_matches:
        #         if el['time'] == last_time:
        #             last_speed = max(el['speed'] if el['speed'] != "?" else last_speed, last_speed)
        #             last_cwnd = max(el['cwnd'] if el['cwnd'] != "?" else last_cwnd, last_cwnd)
        #         else:
        #             writer.writerow({'time': time_i, 'CWND': last_cwnd, 'estimated_speed': last_speed})
        #             time_i+=1
        #             last_speed = max(el['speed'] if el['speed'] != "?" else last_speed, last_speed)
        #             last_cwnd = max(el['cwnd'] if el['cwnd'] != "?" else last_cwnd, last_cwnd)
        #             last_time = el['time']
        #     writer.writerow({'time': time_i, 'CWND': last_cwnd, 'estimated_speed': last_speed})

        # with open(os.getcwd()+ f"/{output_filename_filtr}", mode='w') as csv_file:
        #     field_names = ["time", "CWND", "estimated_speed"]
        #     writer = csv.DictWriter(csv_file, fieldnames=field_names)
        #     writer.writeheader()
        #     last_speed = 0
        #     last_cwnd = 0
        #     last_time = all_matches[0]['time']
        #     time_i = 0
        #     for el in all_matches:
        #         if el['cwnd'] == last_cwnd or el['cwnd'] == "?":
        #             last_speed = max(int(el['speed']) if el['speed'] != "?" else last_speed, last_speed)
        #             last_cwnd = el['cwnd'] if el['cwnd'] != "?" else last_cwnd
        #             last_time = el['time']
        #         else:
        #             writer.writerow({'time': time_i, 'CWND': last_cwnd, 'estimated_speed': last_speed})
        #             time_i+=1
        #             last_speed = int(el['speed']) if el['speed'] != "?" else last_speed
        #             last_cwnd = el['cwnd'] if el['cwnd'] != "?" else last_cwnd
        #             last_time = el['time']

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

    # def forecast_results_from_dmesg(self, experiment)->None:
    #     input_filename = f"{self.input_directory}/{experiment}/{experiment}_dmesg.txt"
    #     output_filename = f"{self.output_directory}/{experiment}/{experiment}_dmesg_forecast.csv"

    #     textfile = open(os.getcwd()+f"/{input_filename}", 'r')
    #     filetext = textfile.read()
    #     print(f"SIZE OF FILETEXT dmesg {len(filetext)}")
    #     textfile.close()
    #     speed_matches = re.findall(".*\d\d:\d\d:\d\d.*forecast CWND=[\d,?]+.*SPEED=\d*", filetext)
    #     speed_matches = [{"time": re.findall("\d\d:\d\d:\d\d", el)[0], "cwnd": "?", "speed": re.findall("\d+", re.findall("SPEED=\d+", el)[0])[0]} for el in speed_matches]
    #     cwnd_matches = re.findall(".*\d\d:\d\d:\d\d.*UPDATE cwnd = \d*", filetext)
    #     cwnd_matches = [{"time": re.findall("\d\d:\d\d:\d\d", el)[0], "cwnd": re.findall("\d+", re.findall("= \d+", el)[0])[0], "speed": "?"} for el in cwnd_matches]
        
    #     all_matches = cwnd_matches + speed_matches
    #     all_matches = sorted(all_matches, key=lambda tcs: tcs['time'])

    #     with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
    #         field_names = ["time", "CWND", "SPEED_CWND"]
    #         writer = csv.DictWriter(csv_file, fieldnames=field_names)
    #         writer.writeheader()
    #         last_speed = 0
    #         last_cwnd = 0
    #         for el in all_matches:
    #             last_speed = el['speed'] if el['speed'] != "?" else last_speed
    #             last_cwnd = el['cwnd'] if el['cwnd'] != "?" else last_cwnd
    #             last_time = el['time']
    #             writer.writerow({'time': last_time, 'CWND': last_cwnd, 'SPEED_CWND': last_speed})
            


if __name__ == '__main__':
    experiment_handler = ExperimentHandler(input_directory="test_output", output_directory="test_output/csv_files")
    for experiment in experiment_handler.experiments:
        os.mkdir(os.getcwd()+f"/{experiment_handler.output_directory}/{experiment}")
        experiment_handler.saving_results_from_iperf(experiment)
        experiment_handler.prepare_pre_final_result(experiment)
        experiment_handler.saving_results_from_dmesg(experiment)
        # experiment_handler.forecast_results_from_dmesg(experiment)
    experiment_handler.save_pre_final_result()
    experiment_handler.save_final_result()
