"""wordcount kernel (Python): port of tasks/wordcount/ref.c."""


def run(data):
    words = 0
    in_word = False
    for c in data:  # iterating bytes yields ints
        if c == 0x20 or 0x09 <= c <= 0x0D:  # space, \t \n \v \f \r
            in_word = False
        elif not in_word:
            in_word = True
            words += 1
    return words


def digest():
    return 0
