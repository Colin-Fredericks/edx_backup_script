import time
import random
import multiprocessing

# Runs the loop that processes things.
# In this example it just waits a random amount of time,
# to simulate projects taking different amounts of time.
def ye_function(inputs, tools):
    # As long as there's something in the input queue,
    while not inputs.empty():
        # Pull an input and a tool off their queues.
        i = inputs.get()
        t = tools.get()
        print("Tool " + t + " starting work on " + str(i))
        # "process" the data (just waiting)
        time.sleep(random.randint(5, 10))
        print("Tool " + t + " finished work on " + str(i))
        # When the tool is ready again, put it back on its queue.
        tools.put(t)
    print("queue empty")
    return True


def run():
    # This is our data. Could be URLs to visit.
    input_queue = multiprocessing.Queue()
    for i in range(0, 20):
        input_queue.put("project " + str(i))

    # These are tools that process the data. Could be webdrivers.
    tool_queue = multiprocessing.Queue()
    tool_list = ["A", "B", "C", "D", "E"]
    for j in tool_list:
        tool_queue.put("tool " + str(j))

    # Spin up several processes, but not more than we have tools.
    # Leave some CPU for other people.
    num_processes = min(len(tool_list), multiprocessing.cpu_count() - 1)
    processes = []

    for n in range(0, num_processes):
        # Creating processes that will run in parallel.
        p = multiprocessing.Process(
            target=ye_function,
            args=(
                input_queue,
                tool_queue,
            ),
        )
        # Track them so we can stop them later.
        processes.append(p)
        # Run the processes.
        p.start()
    for x in processes:
        # Closes out the processes cleanly.
        x.join()


if __name__ == "__main__":
    run()
