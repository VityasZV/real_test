from os import stat
import re
import os
import csv
from collections import defaultdict
from math import sqrt
from save_exp_to_csv_file import ExperimentHandler


"""
Checking series of experiments with equal params of tcp_vityas. Check than our algo is better with probability of 80%
"""

class ExperimentChecker(ExperimentHandler):
    def __init__(self, input_directory: str, output_directory: str):
        super().__init__(input_directory, output_directory)
        self.base_experiments_to_statistic = {}
        tr = ["cubic", "bbr", "bic", "htcp", "highspeed", "illinoise"]
        # self.probabilities = set()

        for e in self.experiments:
            is_traditional = False
            for t in tr:
                if t in e:
                    is_traditional = True
                    break
            if is_traditional: 
                continue
            else:
                if len(re.findall("_e_\d+", e)) != 0:
                    exp = e[0:e.find("_e_")]
                    # self.probabilities.add(int(re.findall("\d+", re.findall("_p_\d+", exp)[0])[0]))
                    # "success" means amount of 'yes' of seria of experiments for each traditional algos
                    if exp not in self.base_experiments_to_statistic.keys():
                        self.base_experiments_to_statistic[exp] = {"amount": 1, "success": {k : {} for k in tr} } # succes[name_of_base_exp (like cubic)][number_of_exp] = better or not (true or false)
                    else:
                        self.base_experiments_to_statistic[exp]["amount"]+=1
    

    def save_super_final_result(self) -> None:
        input_filename = f"{self.input_directory}/result/preparing.csv"
        output_filename = f"{self.input_directory}/result/super_final.csv"
        exp_result = {k: {} for k in self.base_experiments_to_statistic.keys()}
        tr = ["cubic", "bbr", "bic", "htcp", "highspeed", "illinoise"]
        traditional_exp = {k : {} for k in tr}

        # print(f"{traditional_exp}              {exp_result}")
        with open(os.getcwd()+ f"/{input_filename}", mode='r') as csv_file:
            reader = csv.DictReader(csv_file)
            for line in reader:
                exp_base = line["experiment"][0:line["experiment"].find("_e_")]
                exp_number = int(re.findall("\d+", re.findall("_e_\d+", line["experiment"])[0])[0])
                # print(f"LOG {exp_base} {exp_number} of {line}")
                is_traditional = False
                for t in tr:
                    if t in line["experiment"]:
                        traditional_exp[t][exp_number] = int(line["average_bitrate"])
                        is_traditional = True
                        # print(f"tr of {t}: {traditional_exp[t]}")
                        # print(traditional_exp)
                        break
                if is_traditional:
                    continue
                if not is_traditional:
                    exp_result[exp_base][exp_number] = int(line["average_bitrate"])
                    # print(f"base of {exp_base}: {exp_result[exp_base]}")
                    # print(exp_result)
        
        # print(f"trad: {traditional_exp}")
        # print(f"exp: {exp_result}")
        # print()
        # print(f"base: {self.base_experiments_to_statistic}")
        for exp in self.base_experiments_to_statistic.keys():
            for tr_k in traditional_exp.keys():
                for i in range(1, len(traditional_exp[tr_k].keys())+1):
                    if exp_result[exp][i] >= traditional_exp[tr_k][i]:
                        self.base_experiments_to_statistic[exp]["success"][tr_k][i] = True
                    else:
                        self.base_experiments_to_statistic[exp]["success"][tr_k][i] = False
        # print(f"base_exp_to_statistic: {self.base_experiments_to_statistic}")
        probability_to_laplas = {0.8: -1.28, 0.7: -1.03, 0.6: -0.84}  

        with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
            full_better_than={}
            for k in traditional_exp.keys():
                for el in [f"better_than_{k}_{p}" for p in probability_to_laplas.keys()]:
                    full_better_than[el] = ""
            field_names = ["base_experiment", *full_better_than]
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            for e, statistic in self.base_experiments_to_statistic.items():
                for tr_key in traditional_exp.keys():                    
                    for p,l in probability_to_laplas.items():
                        n = statistic["amount"]
                        m = 0
                        for i in range(1, n + 1):
                            if statistic["success"][tr_key][i]:
                                m+=1
                        criterion = sqrt(n)/0.3*(m/n-p)
                        full_better_than[f"better_than_{tr_key}_{p}"] = "yes" if criterion >= l else "no"
                        print(f"m={m}; n={n}; l={l}; p={p}; criterion={criterion}; bt_key={tr_key}; answer={full_better_than[f'better_than_{tr_key}_{p}']}")
                writer.writerow({'base_experiment': e, **full_better_than})



        # better_than = {}.fromkeys(["better_than_" + e for e in traditional_exp],"")

        # probability_to_laplas = {0.8: -1.28, 0.7: -1.03, 0.6: -0.84}  
        
        # print(self.base_experiments_to_statistic)
        # with open(os.getcwd()+ f"/{input_filename}", mode='r') as csv_file:
        #     reader = csv.DictReader(csv_file)
        #     for line in reader:
        #         exp_base = line["experiment"][0:line["experiment"].find("_e_")]
        #         self.base_experiments_to_statistic[exp_base]["amount"] += 1
        #         for b in better_than.keys():
        #             if line[b] == "yes":
        #                 trad_alg_name = b[b.find("better_than_")+len("better_than_"):]
        #                 self.base_experiments_to_statistic[exp_base]["success"][trad_alg_name]+=1
        # print(self.base_experiments_to_statistic)

        # with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
        #     full_better_than={}
        #     for k in better_than.keys():
        #         for el in [k+f"_{p}" for p in probability_to_laplas.keys()]:
        #             full_better_than[el] = ""
        #     field_names = ["base_experiment", *full_better_than]
        #     writer = csv.DictWriter(csv_file, fieldnames=field_names)
        #     writer.writeheader()
        #     for e, statistic in self.base_experiments_to_statistic.items():
        #         for bt_key in better_than.keys():
        #             trad_alg_name = bt_key[bt_key.find("better_than_")+len("better_than_"):]
        #             for p,l in probability_to_laplas.items():
        #                 n = statistic["amount"]
        #                 m = statistic["success"][trad_alg_name]
        #                 criterion = sqrt(n)/0.3*(m/n-p)
        #                 full_better_than[bt_key+f"_{p}"] = "yes" if criterion >= l else "no"
        #                 print(f"m={m}; n={n}; l={l}; p={p}; criterion={criterion}; bt_key={trad_alg_name}; answer={full_better_than[bt_key+f'_{p}'] }")
        #         writer.writerow({'base_experiment': e, **full_better_than})



if __name__ == '__main__':
    print("SUPER FINAL STARTS NOW !!!")   
    experiment_checker = ExperimentChecker(input_directory="test_output", output_directory="test_output/csv_files")
    experiment_checker.save_super_final_result()
    print("SUPER FINAL FINISHED")
