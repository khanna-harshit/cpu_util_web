from django.shortcuts import render, redirect
from django.contrib import messages
import re
import smtplib
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
import csv
import os
import paramiko
import time

# reference

# ['show process cpu', 'show version', 'show platform temperature', 'date',
# 'show system memory', 'show processes memory', 'show interface counters', 'show processes summary', 'docker_stats']


def main(request):
    return render(request, 'app/index.html')


def download(request):
    if request.method == 'POST':

        # inputs from the user
        email = request.POST['email']
        ip_address = request.POST['ip_address']
        start_time = request.POST['start_time']
        end_time = request.POST['end_time']
        username = request.POST['username']
        password = request.POST['password']
        snapshot_count = request.POST['gap']

        # commands that se needed to fetch
        command = ['show processes cpu', 'show version', 'show platform temperature', 'show system-memory',
                   'show processes memory', 'show interface counters', 'date', 'show processes summary',
                   'docker stats  --no-stream']

        if int(snapshot_count) <= 0:
            messages.error(request, "Gap in between two snapshots should greater than 0")
            return redirect('/')
        # initialising variable globally
        month = {'Jan': '01', 'Feb': '02', 'Mar': '03', "Apr": '04', "May": '05', "Jun": '06', "Jul": '07',
                 "Aug": '08', "Sep": '09', "Oct": '10', "Nov": '11', "Dec": '12'}
        line_counter = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        command_running = [False, False, False, False, False, False, False, False, False]
        sep_line = '-----------------------------------------------------------------------------\n\n'
        overall_alert_temp = []
        overall_alert_cpu = []
        date = []
        cpu_graph = []
        temp_graph = []
        temp_sensor_names = []
        memory_graph = []
        docker_stats_graph = []
        docker_stats_sensor_names = []
        try:
            combined_result = ''
            # traversing in list path
            session = paramiko.SSHClient()
            session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            session.connect(ip_address, username=username, password=password)
            for number in range(0, snapshot_count):

                # initialised variables
                print("Taking snapshot : " + str(number + 1))
                result = '\n\n\n'
                process_taken = False
                cpu_taken = False
                cpu_count = 0
                process_count = 0
                counters_dict = {}
                alert_temp = []
                alert_cpu = []
                docker_temp = []
                temp_memory_graph_point = []
                temp_graph_temp = []
                docker_stats_graph_temp = []
                f = ''
                for i in command:
                    (stdin, stdout, stderr) = session.exec_command(i + '\n\n')
                    router_output = stdout.read()
                    f = f + 'admin@sonic:~$ ' + i + '\n\n' + router_output.decode("utf-8") + '\n'
                result_list = f.split('\n')
                counter = 0
                for x in result_list:
                    counter = counter + 1
                    # checking which command starts
                    process_cpu = re.search('show processes cpu', x)
                    version = re.search('show version', x)
                    platform_temperature = re.search('show platform temperature', x)
                    date_1 = re.search('admin', x)
                    date_2 = re.search('date', x)
                    system_memory = re.search('show system-memory', x)
                    processes_memory = re.search('show processes memory', x)
                    interface_counters = re.search('show interface counters', x)
                    processes_summary = re.search('show processes summary', x)
                    docker_stats = re.search('docker stats  --no-stream', x)

                    # to update which command is running
                    if process_cpu:
                        update_command(line_counter, command_running, 0)

                    if version:
                        update_command(line_counter, command_running, 1)

                    if platform_temperature:
                        update_command(line_counter, command_running, 2)

                    if date_1 and date_2:
                        update_command(line_counter, command_running, 3)

                    if system_memory:
                        update_command(line_counter, command_running, 4)

                    if processes_memory:
                        update_command(line_counter, command_running, 5)

                    if interface_counters:
                        update_command(line_counter, command_running, 6)

                    if processes_summary:
                        update_command(line_counter, command_running, 7)

                    if docker_stats:
                        update_command(line_counter, command_running, 8)

                    # show process cpu
                    if command_running[0]:
                        index = 0
                        ans = show_process_cpu(index, cpu_taken, cpu_count, x, line_counter, sep_line, cpu_graph)
                        result += ans[0]
                        cpu_taken = ans[1]
                        cpu_count = ans[2]
                        if ans[3] != '-1':
                            alert_cpu.append(x)

                    # show version
                    if command_running[1]:
                        index = 1
                        result += show_version(index, x, line_counter, sep_line)

                    # show platform temperature
                    if command_running[2]:
                        index = 2
                        ans = show_platform_temperature(index, x, line_counter, sep_line)
                        result += ans[0]
                        if ans[1] != '-1':
                            alert_temp.append(x)
                        if ans[2] != '-1':
                            lst = x.split()
                            if len(lst) >= 9:
                                if len(temp_graph) == 0:
                                    temp_sensor_names.append(lst[0])
                                temp_graph_temp.append(float(lst[1]))

                    # date
                    if command_running[3]:
                        index = 3
                        ans = show_date(index, x, line_counter, sep_line)
                        result += ans[0]
                        if ans[1] != '-1':
                            date.append(ans[1])
                    # show system memory
                    if command_running[4]:
                        index = 4
                        a = re.search('Mem:', x)
                        if a:
                            lst = x.split()
                            temp_memory_graph_point.append(int(lst[1]))
                            temp_memory_graph_point.append(int(lst[2]))
                            temp_memory_graph_point.append(int(lst[3]))
                        result += show_system_memory(index, x, line_counter, sep_line)

                    # show processes memory
                    if command_running[5]:
                        index = 5
                        ans = show_processes_memory(index, process_taken, process_count, x, line_counter, sep_line)
                        result += ans[0]
                        process_taken = ans[1]
                        process_count = ans[2]

                    # show interface counters
                    if command_running[6]:
                        index = 6
                        result += show_interface_counters(counters_dict, index, x, line_counter, sep_line)

                    if command_running[7]:
                        pass

                    # docker stats
                    if command_running[8]:
                        index = 8
                        ans = show_docker_stats(index, x, line_counter, sep_line)
                        result += ans[0]
                        if ans[1] != '-1':
                            lst = x.split()
                            if len(lst) == 14:
                                if len(docker_stats_graph) == 0:
                                    docker_stats_sensor_names.append(lst[1])
                                docker_stats_graph_temp.append(float(lst[2][:-1]))

                docker_stats_graph.append(docker_stats_graph_temp)
                combined_result += '\n\n\n######################################################################\n\n'
                combined_result += 'from snapshot ' + str(number + 1) + ' ----> ' + str(number) + '\n\n'
                combined_result += '######################################################################'
                combined_result += result
                temp_graph.append(temp_graph_temp)
                memory_graph.append(temp_memory_graph_point)
                overall_alert_cpu.append(alert_cpu)
                overall_alert_temp.append(alert_temp)

            # alert
            # alert(overall_alert_temp, overall_alert_cpu)
            # plot_cpu(cpu_graph, date)
            # plot_temp(temp_graph, temp_sensor_names, date)
            # plot_memory(memory_graph, date)
            # plot_docker(docker_stats_graph, docker_stats_sensor_names, cpu_graph, date)
            to_csv(temp_graph, temp_sensor_names, cpu_graph, memory_graph, date, docker_stats_graph,
                       docker_stats_sensor_names, month)
            final_result = '\n\n########################################################################## \n\n'
            final_result += min_max_average(temp_graph, temp_sensor_names, cpu_graph, memory_graph,
                                            docker_stats_graph,
                                            docker_stats_sensor_names)
            final_result += combined_result
            text_file(final_result)

            # Closing the connection
            session.close()
            return render(request, 'app/result.html')


        except:
            print(
                "* Invalid username or password :( \n* Please check the username/password file or the device configuration.")
            print("* Closing program... Bye!")
            messages.error(request, "Ip Address OR Username OR Password is wrong")
            return redirect('/')


    return render(request, 'app/index.html')


# average
def average(lst):
    sum_of_list = 0
    for i in range(0, len(lst)):
        sum_of_list += lst[i]
    avg = sum_of_list / len(lst)
    return avg


# minimum maximum average
def min_max_average(temp_graph, temp_sensor_names, cpu_graph, memory_graph, docker_stats_graph, docker_stats_sensor_names):
    result = ''
    # cpu data
    result += 'CPU usage data' + '\n'
    result += 'minimum CPU usage ' + str(min(cpu_graph)) + '\n'
    result += 'maximum CPU usage ' + str(max(cpu_graph)) + '\n'
    result += 'average CPU usage ' + str(average(cpu_graph)) + '\n\n'

    # temperature data

    result += "Temperature data\n"
    for i in range(0, len(temp_sensor_names)):
        temporary = []
        for j in range(0, len(temp_graph)):
            temporary.append(temp_graph[j][i])

        result += temp_sensor_names[i] + ' Temperature data' + '\n'
        result += 'minimum' + temp_sensor_names[i] + ' temperature ' + str(min(temporary)) + '\n'
        result += 'maximum' + temp_sensor_names[i] + ' temperature ' + str(max(temporary)) + '\n'
        result += 'average' + temp_sensor_names[i] + ' temperature ' + str(round(average(temporary), 3)) + '\n\n'

    # memory data
    total_list = []
    used_list = []
    free_list = []
    other_list = []
    for i in range(0, len(memory_graph)):
        total_list.append(memory_graph[i][0])
        used_list.append(memory_graph[i][1])
        free_list.append(memory_graph[i][2])
        other_list.append(memory_graph[i][0] - memory_graph[i][1] - memory_graph[i][2])

    result += 'memory data' + '\n'
    result += 'Total ---> Minimum ' + str(min(total_list)) + ' Maximum ' + str(max(total_list)) + ' Average ' + str(
        round(average(total_list), 3)) + '\n'
    result += 'Used  ---> Minimum ' + str(min(used_list)) + ' Maximum ' + str(max(used_list)) + ' Average ' + str(
        round(average(used_list), 3)) + '\n'
    result += 'Free  ---> Minimum ' + str(min(free_list)) + ' Maximum ' + str(max(free_list)) + ' Average ' + str(
        round(average(free_list), 3)) + '\n'
    result += 'Other ---> Minimum ' + str(min(other_list)) + ' Maximum ' + str(max(other_list)) + ' Average ' + str(
        round(average(other_list), 3)) + '\n\n'

    # docker stats data
    result += 'docker stats data' + '\n'
    for i in range(0, len(docker_stats_graph[0])):
        temporary = []
        for j in range(0, len(docker_stats_graph)):
            temporary.append(docker_stats_graph[j][i])
        result += docker_stats_sensor_names[i] + '   ---> Minimum ' + str(min(temporary)) + ' Maximum ' + str(max(temporary)) + ' Average ' + str(
            round(average(temporary), 3)) + '\n'
    return result

# create csv files
def to_csv(temp_graph, temp_sensor_names, cpu_graph, memory_graph, date, docker_stats_graph, docker_stats_sensor_names, month):
    # to convert date string to datetime object
    date_ = []
    for i in date:
        lst = i.split()
        str = ''
        str += month[lst[2]]
        str += '/'
        str += lst[1]
        str += '/'
        str += lst[3][2:]
        datetime_str = str + " " + lst[4]
        # datetime_object = datetime.strptime(datetime_str, '%m/%d/%y %H:%M:%S')
        date_.append(i)

    # store temp_graph data
    temp_list = []
    # store docker_graph data
    docker_list = []
    # store cpu_usage data
    cpu_list = []
    # store memory_usage data
    memory_list = []
    for i in range(0, len(temp_graph)):
        temporary = []
        for j in range(0, len(temp_graph[0])):
            temporary.append(temp_graph[i][j])
        temporary.append(date_[i])
        temp_list.append(temporary)
    for i in range(0, len(date)):
        cpu_list.append([cpu_graph[i], date_[i]])
    for i in range(0, len(docker_stats_graph)):
        temporary = []
        for j in range(0, len(docker_stats_graph[0])):
            temporary.append(docker_stats_graph[i][j])
        temporary.append(cpu_graph[i])
        temporary.append(date_[i])
        docker_list.append(temporary)

    for i in range(0, len(date)):
        memory_list.append([date_[i], memory_graph[i][0], memory_graph[i][1], memory_graph[i][2],
                            memory_graph[i][0] - memory_graph[i][1] - memory_graph[i][2]])

    # header of temperature
    header_temp = []
    for i in temp_sensor_names:
        header_temp.append(i)
    header_temp.append('Time')
    # header of cpu_usage
    header_cpu = ['CPU usage percentage', 'Time']
    # header of memory_usage
    header_memory = ['Time', 'Total', 'Used', 'Free', 'Other']
    # header of docker stats
    header_docker = docker_stats_sensor_names
    header_docker.append('System CPU%')
    header_docker.append('Time')

    # make directory for showing output
    CURR_DIR = os.getcwd()
    if not os.path.exists(CURR_DIR + '\output'):
        os.mkdir(CURR_DIR + '\output', mode=0o666)
    if not os.path.exists(CURR_DIR + '\output\csv'):
        os.mkdir(CURR_DIR + '\output\csv', mode=0o666)

    # creating and storing data in temp_graph_PSU1.csv
    f1 = open(CURR_DIR + '/output/csv/temp_graph.csv', 'w')
    writer = csv.writer(f1)
    writer.writerow(header_temp)
    writer.writerows(temp_list)

    # creating and storing data in cpu_usage.csv
    f2 = open(CURR_DIR + '/output/csv/cpu_usage.csv', 'w')
    writer = csv.writer(f2)
    writer.writerow(header_cpu)
    writer.writerows(cpu_list)

    # creating and storing data in memory_usage.csv
    f3 = open(CURR_DIR + '/output/csv/memory_usage.csv', 'w')
    writer = csv.writer(f3)
    writer.writerow(header_memory)
    writer.writerows(memory_list)

    # creating and storing data in memory_usage.csv
    f4 = open(CURR_DIR + '/output/csv/docker_stats.csv', 'w')
    writer = csv.writer(f4)
    writer.writerow(header_docker)
    writer.writerows(docker_list)


# creating result.txt
def text_file(combined_result):
    f = open("result.txt", "w+")
    f.write(combined_result)
    f.close()


# plotting docker stats graph
def plot_docker(docker_stats_graph, docker_stats_sensor_names, cpu_graph, date):
    date_ = []
    for i in range(1, len(date) + 1):
        datetime_str = 5 * i
        date_.append(datetime_str)
    for i in range(0, len(docker_stats_graph[0])):
        temp = []
        for j in range(0, len(docker_stats_graph)):
            temp.append(docker_stats_graph[j][i])
        barWidth = 0.25
        plt.figure(i + 10000)
        # Set position of bar on X axis
        plt.title(docker_stats_sensor_names[i] + ' graph with staring time ' + str(date[0]))
        br1 = np.arange(len(temp))
        br2 = [x + barWidth for x in br1]
        # Make the plot
        plt.bar(br1, temp, color='r', width=barWidth,
                edgecolor='grey', label='docker cpu %')
        plt.bar(br2, cpu_graph, color='limegreen', width=barWidth,
                edgecolor='grey', label='system cpu %')

        # giving alert line
        plt.axhline(y=50, color='r', linestyle='--', label='alert line')
        # Adding Xticks
        plt.xlabel('docker cpu % , system cpu %', fontweight='bold', fontsize=15)
        plt.ylabel('cpu %', fontweight='bold', fontsize=15)
        plt.xticks([r + barWidth for r in range(len(temp))], date_, fontsize=4)
        plt.legend(loc='upper left', prop={'size': 4}, bbox_to_anchor=(1, 1))


# plotting memory graphs
def plot_memory(memory_graph, date):
    for i in range(0, len(memory_graph)):
        # defining labels
        activities = ['used', 'free', 'other']
        # portion covered by each label
        slices = []
        for j in range(1, len(memory_graph[i])):
            slices.append(memory_graph[i][j])
        slices.append(memory_graph[i][0] - slices[0] - slices[1])
        # color for each label
        colors = ['coral', 'yellowgreen', 'aqua']
        # plotting the pie chart

        txt = 'Total : ' + str(memory_graph[i][0]) + ', Used : ' + str(slices[0]) + ', Free : ' + str(
            slices[1]) + ', other : ' + str(slices[2])
        plt.figure(i + 1000)
        plt.title("Memory plot at " + str(date[i]))
        plt.pie(slices, labels=activities, colors=colors,
                startangle=90, explode=(0, 0.1, 0),
                radius=1.2, autopct='%1.1f%%')
        # plotting legend
        plt.legend(loc='upper left', prop={'size': 4}, bbox_to_anchor=(1, 1))
        plt.text(-1.5, -1.55, txt, {'color': 'C0', 'fontsize': 13})


# plotting temperature graph
def plot_temp(temp_graph, temp_sensor_names, date):
    date_ = []
    for i in date:
        lst = i.split()
        str = ''
        str += month[lst[2]]
        str += '/'
        str += lst[1]
        str += '/'
        str += lst[3][2:]
        datetime_str = str + " " + lst[4]
        datetime_object = datetime.strptime(datetime_str, '%m/%d/%y %H:%M:%S')
        date_.append(datetime_object)
    for i in range(0, len(temp_sensor_names)):
        temporary = []
        for j in range(0, len(temp_graph)):
            temporary.append(temp_graph[j][i])
        plt.figure(i + 2)
        plt.plot(date_, temporary, marker="o", label=temp_sensor_names[i])
        # beautify the x-labels
        plt.gcf().autofmt_xdate()
        # giving alert line
        plt.axhline(y=50, color='r', linestyle='--', label='alert line')
        # naming the x-axis
        plt.xlabel('Date Time')
        # naming the y-axis
        plt.ylabel('temp')
        # giving a title to my graph
        plt.title('Temperature plot ' + temp_sensor_names[i])
        plt.legend(loc='upper left', prop={'size': 4}, bbox_to_anchor=(1, 1))


# plotting cpu usage graph
def plot_cpu(cpu_graph, date):
    # plotting the points
    date_ = []
    for i in date:
        lst = i.split()
        str = ''
        str += month[lst[2]]
        str += '/'
        str += lst[1]
        str += '/'
        str += lst[3][2:]
        datetime_str = str + " " + lst[4]
        datetime_object = datetime.strptime(datetime_str, '%m/%d/%y %H:%M:%S')
        date_.append(datetime_object)
        # plotting graph
    plt.figure(1)
    plt.plot(date_, cpu_graph, marker="o", label='cpu%')
    # beautify the x-labels
    plt.gcf().autofmt_xdate()
    # naming the x-axis
    plt.xlabel('Date Time')
    # naming the y-axis
    plt.ylabel('CPU%')
    # giving alert line
    plt.axhline(y=15, color='r', linestyle='--', label='alert line')
    # giving a title to my graph
    plt.title('CPU USAGE')
    plt.legend(loc='upper left', prop={'size': 4}, bbox_to_anchor=(1, 1))


# alert
def alert(overall_alert_temp, overall_alert_cpu):
    try:
        # Create your SMTP session
        smtp = smtplib.SMTP('smtp.gmail.com', 587)

        # Use TLS to add security
        smtp.starttls()

        # User Authentication
        smtp.login("cpuutil@gmail.com", "dciogtkivlexlrrd")

        # Defining The Message

        SUBJECT = 'Warning !!'
        start_temp = False
        start_cpu = False
        text = 'warning and danger !! \n\n\n'
        for i in range(0, len(overall_alert_temp)):
            if len(overall_alert_temp[i]) != 0:
                if not start_temp:
                    start_temp = True
                    text += 'SHOW PLATFORM TEMPERATURE \n\n\n'
                text += '   ' + date[i] + '\n\n'
            for j in range(0, len(overall_alert_temp[i])):
                lst = overall_alert_temp[i][j].split()
                text += '       ' + lst[0] + ' has a temperature of ' + lst[1] + '\n'
            text += '\n\n'
        for i in range(0, len(overall_alert_cpu)):
            if len(overall_alert_cpu[i]) != 0:
                if not start_cpu:
                    start_cpu = True
                    text += 'SHOW PROCESS CPU \n\n\n'
                text += '   ' + date[i] + '\n\n'
            for j in range(0, len(overall_alert_cpu[i])):
                lst = overall_alert_cpu[i][j].split()
                text += '       ' + lst[11] + ' has a CPU temperature of ' + lst[
                    8] + ' and has a MEM temperature of ' + lst[9] + '\n'
            text += '\n\n'

        message = 'Subject: {}\n\n{}'.format(SUBJECT, text)

        # Sending the Email
        if start_temp or start_cpu:
            smtp.sendmail("cpuutil@gmail.com", "harshit.19B101021@abes.ac.in", message)

        # Terminating the session
        smtp.quit()

    except Exception as ex:
        print("Something went wrong....", ex)


# update command
def update_command(line_counter, command_running, index):
    for ele in range(0, len(line_counter)):
        line_counter[ele] = 0
        command_running[ele] = False
    line_counter[index] += 1
    command_running[index] = True


# show process cpu
def show_process_cpu(index, cpu_taken, cpu_count, x, line_counter, sep_line, cpu_graph):
    result = ''
    alert_ = '-1'
    if line_counter[index] == 1:
        result += sep_line
        result += 'show process cpu\n\n'
    line_counter[index] += 1
    a = re.search("%Cpu", x)
    b = re.search('MiB Mem :', x)
    c = re.search('PID', x)
    if a:
        result += x + '\n'
        cpulist = x.split()
        cpu_graph.append(float(cpulist[3]))
    if b:
        result += x + '\n'
    if c:
        cpu_taken = True
    if cpu_taken and cpu_count < 4:
        result += x
        if cpu_count > 0:
            lst = x.split()
            cpu = lst[8]
            mem = lst[9]
            if float(cpu) >= 50 or float(mem) >= 50:
                alert_ = x
        cpu_count += 1
        if cpu_count == 4:
            result += '\n\n\n'
    return [result, cpu_taken, cpu_count, alert_]


# show version
def show_version(index, x, line_counter, sep_line):
    result = ''
    if line_counter[index] == 1:
        result += sep_line
        result += 'show version\n\n'
    line_counter[1] += 1
    a = re.search("SONiC Software Version:", x)
    b = re.search('Platform:', x)
    c = re.search('HwSKU: ', x)
    d = re.search("ASIC:", x)
    e = re.search('Serial Number:', x)
    f = re.search('Uptime:', x)
    if a:
        result += x
    if b:
        result += x
    if c:
        result += x
    if d:
        result += x
    if e:
        result += x
    if f:
        result += x + '\n\n\n'
    return result


# show platform temperature
def show_platform_temperature(index, x, line_counter, sep_line):
    result = ''
    alert_ = '-1'
    add_or_not = '-1'
    if line_counter[index] == 1:
        result += sep_line
        result += 'show platform temperature\n\n'
    line_counter[index] += 1
    if line_counter[index] >= 5:
        add_or_not = x
    a = re.search('True', x)
    if line_counter[index] >= 3:
        result += x
    if a:
        alert_ = x
    return [result, alert_, add_or_not]


# show date
def show_date(index, x, line_counter, sep_line):
    result = ''
    date_and_time = '-1'
    if line_counter[index] == 1:
        result += sep_line
        result += 'date\n\n'
    line_counter[index] += 1
    a = re.search('UTC', x)
    if a:
        result += x + '\n\n\n'
        date_and_time = x
    return [result, date_and_time]


# show system memory
def show_system_memory(index, x, line_counter, sep_line):
    result = ''
    if line_counter[index] == 1:
        result += sep_line
        result += 'show system memory\n\n'

    line_counter[index] += 1
    a = re.search("total", x)
    b = re.search('Mem:', x)

    if a:
        result += x
    if b:
        result += x + '\n\n\n'
    return result


# show docker stats
def show_docker_stats(index, x, line_counter, sep_line):
    result = ''
    add_or_not = '-1'
    if line_counter[index] == 1:
        result += sep_line
        result += 'show docker stats\n\n'
    line_counter[index] += 1
    if line_counter[index] >= 4:
        add_or_not = x
    if line_counter[index]>=3:
        result += x + '\n'
    return [result, add_or_not]


# show processes memory
def show_processes_memory(index, process_taken, process_count, x, line_counter, sep_line):
    result = ''
    if line_counter[index] == 1:
        result += sep_line
        result += 'show processes memory\n\n'
    line_counter[index] += 1
    a = re.search("%Cpu", x)
    b = re.search('MiB Mem :', x)
    c = re.search('PID', x)

    if a:
        result += x + '\n'
    if b:
        result += x + '\n'
    if c:
        process_taken = True
    if process_taken and process_count < 4:
        result += x
        process_count += 1
        if process_count == 4:
            result += '\n\n\n'
    return [result, process_taken, process_count]


# show interface counters
def show_interface_counters(counters_dict, index, x, line_counter, sep_line):
    result = ''
    a = re.search('U', x)
    b = re.search('D', x)
    if a or b:
        if line_counter[index] == 1:
            result += sep_line
            result += 'show system memory\n\n'
        line_counter[index] += 1
        lst = x.split()
        counters_dict[lst[0]] = [lst[1], lst[2], lst[8]]
        i = lst[0]
        j = [lst[1], lst[2], lst[3]]
        new_i = i
        for length in range(len(i), 15):
            new_i += ' '
        result += new_i
        for item in j:
            new_item = item
            for length in range(len(item), 15):
                new_item += ' '
            result += new_item
        result += '\n'
    return result


def save_multi_image():
    # make directory for showing output
    CURR_DIR = os.getcwd()
    if not os.path.exists(CURR_DIR + '\output'):
        os.mkdir(CURR_DIR + '\output', mode=0o666)
    if not os.path.exists(CURR_DIR + '\output\graphs'):
        os.mkdir(CURR_DIR + '\output\graphs', mode=0o666)
    p1 = PdfPages(CURR_DIR + '/output/graphs/memory_graphs.pdf')
    p2 = PdfPages(CURR_DIR + '/output/graphs/cpu_graphs.pdf')
    p3 = PdfPages(CURR_DIR + '/output/graphs/docker_graphs.pdf')
    p4 = PdfPages(CURR_DIR + '/output/graphs/temp_graphs.pdf')
    p5 = PdfPages(CURR_DIR + '/output/graphs/Graphs.pdf')
    fig_nums = plt.get_fignums()
    memory = []
    cpu = []
    temp = []
    docker = []
    combined = []
    for n in fig_nums:
        combined.append(plt.figure(n))
        if n >= 10000:
            docker.append(plt.figure(n))
        elif n >= 1000:
            memory.append(plt.figure(n))
        elif n >= 2:
            temp.append(plt.figure(n))
        else:
            cpu.append(plt.figure(n))
    for fig in memory:
        fig.savefig(p1, format='pdf')
    for fig in docker:
        fig.savefig(p3, format='pdf')
    for i in temp:
        i.savefig(p4, format='pdf')
    for i in cpu:
        i.savefig(p2, format='pdf')
    for i in combined:
        i.savefig(p5, format='pdf')

    p1.close()
    p2.close()
    p3.close()
    p4.close()
    p5.close()

