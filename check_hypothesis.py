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
        self.base_experiments_to_statistic = defaultdict(dict)
        tr = ["cubic", "bbr", "bic", "htcp", "highspeed", "illinoise"]
        # self.probabilities = set()

        for e in self.experiments:
            if e.find("_e_") != -1:
                exp = e[0:e.find("_e_")]
                # self.probabilities.add(int(re.findall("\d+", re.findall("_p_\d+", exp)[0])[0]))
                # "success" means amount of 'yes' of seria of experiments for each traditional algos
                self.base_experiments_to_statistic[exp] = {"amount": 0, "success": defaultdict(int).fromkeys(tr, 0)}
    

    def save_super_final_result(self) -> None:
        input_filename = f"{self.input_directory}/result/final.csv"
        output_filename = f"{self.input_directory}/result/super_final.csv"
        exp_result = {}
        tr = ["cubic", "bbr", "bic", "htcp", "highspeed", "illinoise"]
        traditional_exp = {}.fromkeys(tr, 0.0)
        better_than = {}.fromkeys(["better_than_" + e for e in tr],"")
        probability_to_laplas = {0.9: -1.64, 0.8: -1.28, 0.7: -1.03}
        print(self.base_experiments_to_statistic)
        with open(os.getcwd()+ f"/{input_filename}", mode='r') as csv_file:
            reader = csv.DictReader(csv_file)
            for line in reader:
                exp_base = line["experiment"][0:line["experiment"].find("_e_")]
                self.base_experiments_to_statistic[exp_base]["amount"] += 1
                for b in better_than.keys():
                    if line[b] == "yes":
                        trad_alg_name = b[b.find("better_than_")+len("better_than_"):]
                        self.base_experiments_to_statistic[exp_base]["success"][trad_alg_name]+=1
        print(self.base_experiments_to_statistic)

        with open(os.getcwd()+ f"/{output_filename}", mode='w') as csv_file:
            full_better_than={}
            for k in better_than.keys():
                for el in [k+f"_{p}" for p in probability_to_laplas.keys()]:
                    full_better_than[el] = ""
            field_names = ["base_experiment", *full_better_than]
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            writer.writeheader()
            for e, statistic in self.base_experiments_to_statistic.items():
                for bt_key in better_than.keys():
                    trad_alg_name = bt_key[bt_key.find("better_than_")+len("better_than_"):]
                    for p,l in probability_to_laplas.items():
                        n = statistic["amount"]
                        m = statistic["success"][trad_alg_name]
                        criterion = sqrt(n)/0.3*(m/n-p)
                        full_better_than[bt_key+f"_{p}"] = "yes" if criterion >= l else "no"
                        print(f"m={m}; n={n}; l={l}; p={p}; criterion={criterion}; bt_key={trad_alg_name}; answer={full_better_than[bt_key+f'_{p}'] }")
                writer.writerow({'base_experiment': e, **full_better_than})



if __name__ == '__main__':
    print("SUPER FINAL STARTS NOW !!!")   
    experiment_checker = ExperimentChecker(input_directory="test_output", output_directory="test_output/csv_files")
    experiment_checker.save_super_final_result()
    print("SUPER FINAL FINISHED")
