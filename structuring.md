---
author: Iddo Lev
last_update: 2026-03-09
---

# Correct Structuring

<a id="order"/>

## 1. Order

1. Put the smaller `if` case first

E.g. instead of

```python
def func(x):
    if some_condition(x):
        do_1(x)
        do_2(x)
        ... # long sequence of lines
        do_n(x)
    return x
```

Use:

```python
def func(x):
    if not some_condition(x):
        return x
    do_1(x)
    # long sequence of lines
    do_n(x)
    return x
```

(This has less indentation, and is easier to debug).

<a id="default-values"/>

## 2. Default Values

1. Usually it's bad practice to have a boolean parameter of a function have a default value of True because not mentioning the parameter gives it a value of True which usually means some positive action that happens where the called might not be aware of it. See if you can rename the parameter to mean the opposite, with a default value False.

<a id="end-cases"/>

## 3. End cases

Your code should handle all end cases. In particular:

1. Don't assume correct input. Check for it. Either:
   1. If an incorrect input may be encountered during runtime, check for it and if needed, raise ValueError or some other appropriate Exception.
   2. If an incorrect input cannot be encountered during runtime but only during development, you can use assert to verify that this is true. Don't use assert statements to check for runtime errors \- Python code can be compiled while removing such statements.
2. Don't end a sequence of if \- elif statements with elif. It should almost always end with else (except for very rare cases). If you are handling a few cases, each with its own if/elseif, and there is supposed to be no "else case", then raise NotImplementedError() as the else case.

<a id="don't-repeat-yourself"/>

## 4. Don't Repeat Yourself

[Don't Repeat Yourself](https://en.wikipedia.org/wiki/Don%27t_repeat_yourself) (DRY): If you see that two sections of code are very similar, factor out the common parts to a function, and call it twice with the different values.

<a id="example-1"/>

### 4.1. Example 1

Here is some code using DataFrames:

```python
if not some_cond:
    df[out] = df[column].apply(lambda x: x >= min_value and x < max_value) & df[out]
else:
    df[out] = df[column].apply(lambda x: x < min_value or x >= max_value) & df[out]
```

It can be simplified to:

```python
def in_range(x):
    return min_value <= x < max_value
modifier = df[column].apply(in_range)
if some_cond:
    modifier = ~modifier
df[out] &= modifier
```

The main idea demonstrated here: The two cases are very similar. The shared parts (i.e. applying a function on a column, modifying df\[out\]) are factored out and written just once.

Other ideas demonstrated here:

1. Instead of: X \>= Y and X \<= Z, you can use: Y \<= X \<= Z.
2. Instead of: X \= X op Y, you can use: X op= Y.
   1. Above: df\[out\] &= modifier instead of: df\[out\] \= modifier & df\[out\]
3. Don't write yourself the negation of a condition \- let the code do it for you
   1. Above: in\_range is written once, and the negation is calculated using \~.

<a id="example-2"/>

### 4.2. Example 2

Here are three similar functions, where node gets an instance of a class that inherits from Node.

```python
def foo_node_a(data: pd.DataFrame, node: NodeA):
    data[col] = data[data[col] == node.value]
def foo_node_b(data: pd.DataFrame, node: NodeB):
    data[col] = data[data[col].in(node.values)]
def foo_node_c(data: pd.DataFrame, node: NodeC):
    data[col] = data[data[col] <= node.max_value]
```

How can we use DRY here? Factor out the common part, and move the different part to the specific node class:

```python
def foo_node(data: pd.DataFrame, node: Node):
    data[col] = data[data[col].apply(node.condition)]

class Node:
    def condition(self, x) -> bool:
        raise NotImplementedError()

class NodeA(Node):
    def condition(self, x) -> bool:
        return x == self.value

class NodeB(Node):
    def condition(self, x) -> bool:
        return x in self.values

class NodeC(Node):
    def condition(self, x) -> bool:
        return x <= self.max_value
```

Why is this better?

1. It separates the logic of the main procedure (foo\_node) from the logic that differs between the classes.
2. If in the future we add another child of Node, it will be easier to add just the part it does differently (the condition method).

<a id="utilities-instead-of-code-idioms"/>

## 5. Utilities Instead of Code Idioms

A "[code Idiom](https://en.wikipedia.org/wiki/Programming_idiom)" is a syntactic fragment that recurs frequently across software projects and has a single semantic role. For example in Python, writing a string text into to a text file path path, while ensuring the path exists:

```python
import os
import pathlib
path_folder = os.path.dirname(path)
pathlib.Path(path).mkdir(parents=True, exist_ok=True)
with open(path, 'w') as f:
    f.write(text)
```

Such "code idioms" should be avoided because it doesn't make sense that every place requiring this functionality will contain it from scratch. That's why we implemented a [utilities repository](https://gitlab.com/evolution-inc/utilities) that wraps such low-level functions with logical operations, e.g.: ensure\_path, save\_text\_file, delete\_path, etc.

This idea is a special case of the general principle [Don't Repeat Yourself](#don't-repeat-yourself).

See also: [Documentation of Utilities](https://docs.google.com/document/d/1fe_HXnh0lC7_AyKn461zX8g2kxpioEBr_JX7gpGaRMI/edit#heading=h.n4v8ejq297u6).

<a id="write-logic-level-/-high-level-code"/>

## 6. Write Logic-Level / High-Level Code

Python is a very high-level, flexible programming language, which means that a lot of the results you would like to achieve can be done using very succinct code that relies on high-level operations. Many such operations are already given to you in Python or one of the libraries.

Here is an example of a refactor in our code. Suppose you have a dictionary from line id to list of elements, and you want to return a dictionary from line id to the first largest element of the id's elements list. Each element has a start and end position, and the element's length is defined as: 1+end-start.

The original code:

```python
found_matches = {}
for line, values in section.items():
    max_length_in_line = 0
    final_value = []
    for value in values:
        match_length = value.end_pos - value.start_pos
        if max_length_in_line <= match_length:
            max_length_in_line = match_length
            final_value = value
    found_matches[line] = final_value
return found_matches
```

In the above code, the reader needs to read it carefully to understand what it's doing.
Here's the refactored code:

```python
found_matches = {line_num: self.first_longest_element(values)
                 for line_num, values in section.items()}
```

In this code, you can easily see at a high-level the main thing the code is doing: applying first\_longest\_element on each value of the dict. I.e. you clearly see the two main things: the algorithm (for-loop on a dict), and the inner operation (first\_longest\_element). Also, the operation has a descriptive name which clearly shows what it does. Now we add:

```python
def first_longest_element(values: List[TagElement]) -> TagElement:
    return max(values, key=TagElement.__len__)
```

Here, instead of doing this calculation using low-level operations (remembering the max value seen so far, comparing using \<=, etc.), we use the high-level operator max. If we don't want max directly on the value, we can use the key argument and give it:
`lambda element: 1 + element.end - element.pos`
But that is too specific to be defined here \- according to OOP, the property of an element (such as its length) should be defined on the class itself. So we add a \_\_len\_\_ method to the TagElement class.

<a id="encapsulation"/>

## 7. Encapsulation

Encapsulation is a basic principle of [Object Oriented Programming](https://en.wikipedia.org/wiki/Object-oriented_programming) (OOP). Read about [encapsulation](https://en.wikipedia.org/wiki/Encapsulation_\(computer_programming\)), and related concepts: [disadvantages of tight coupling](https://en.wikipedia.org/wiki/Coupling_\(computer_programming\)#Disadvantages_of_tight_coupling), [information hiding](https://en.wikipedia.org/wiki/Information_hiding), [separation of concerns](https://en.wikipedia.org/wiki/Separation_of_concerns), [modular design](https://en.wikipedia.org/wiki/Modular_design).

The main idea is to put inside a class all members and methods that are relevant for the class, instead of spreading it around over different functions or places.

<a id="put-in-a-class"/>

### 7.1. Put in a class

**All queries about a class that depend only on the class content should be a method**
Sometimes when we define a class, we don't yet define all methods that will be useful for that class. Don't take the current definition of the class as Torah from Sini, you can add new methods as needed.

For example, in IES, we defined the class LexicalElement, which is created when a LexicalEntry matches some piece of text. LexicalElement contains a member tokens: List\[Token\]. At some point, we wanted to get the text obtained by concatenating the texts of a LexicalElement's tokens.

The wrong way to do it is to rely on line\_tokens, the entire list of tokens of the line where the LexicalElement was found, and use:

```python
' '.join([token.lower for token in
          line_tokens[element.start_pos: element.end_pos + 1]])
```

Instead, the moment you see that you need such a functionality, and realize that all the information is contained in the class, and that this functionality could be used elsewhere, then add in LexicalElement:

```python
def tokens_text(self) -> str:
    return ' '.join(token.lower for token in self.tokens)
```

and then simply use element.tokens\_text().

<a id="information-hiding"/>

### 7.2. Information Hiding

[Information Hiding](https://en.wikipedia.org/wiki/Information_hiding) is the principle of segregating the design decisions of a piece of code that are most likely to change, thus protecting other parts of the program from extensive modification if the design decision is changed. The protection involves providing a stable interface which protects the remainder of the program from the implementation (whose details are likely to change).

**Don't access private members**
For example, class Foo contains a member dc which is a dictionary.

Instead of accessing this member directly:

```python
x = Foo(...)
x.dc.get(value)
```

define an accessor:

```python
class Foo:
    def get_dc_value(self, value):
        return self._dc.get(value)

x = Foo(...)
x.get_dc_value(value)
```

Note: To protect Foo from misuse, name the dictionary member \_dc, using the Python [convention](#6.1.2.-underscore-indicates-private-member/method) that underscore indicates a private member.

Even more crucial is avoiding assigning a value to a member of a class.
Instead of:

```python
X.dc = value
```

use:

```python
x.set_dc(value)
```

<a id="use-class-members-instead-of-passing-values-around"/>

### 7.3. Use class members instead of passing values around

For example, you have a for-loop that goes over some items, and does some calculation. You put this calculation in a separate function according to the principle "[Break Long/Complex Sections Into Smaller Blocks](#2.2.3.-break-long/complex-sections-into-smaller-blocks)". But you need some variables that may be affected between iterations of the for-loop. So instead of this:

```python
some_var = False
for item in items:
    some_var = func(item, some_var)

def func(item: Item, some_var: bool) -> bool:
    ...   # code that may change some_var
    return some_var
```

Do this:

```python
class SomeClass:
    def run(self):
        self.some_var = False   # or possibly initialize in SomeClass's constructor
        for item in items:
            self.func(item)

    def func(self, item: Item) -> None:
        ...   # code that may change self.some_var
```

<a id="single-responsibility-principle"/>

## 8. Single-Responsibility Principle

The [Single-Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle) (SRP) states that every module, class or function in a computer program should have responsibility over a single part of that program's functionality, and it should [encapsulate](#encapsulation) that part.

It is related to the principle of [Separation of Concerns](https://en.wikipedia.org/wiki/Separation_of_concerns) (SOC), and is one of the five [SOLID](https://en.wikipedia.org/wiki/SOLID) principles.

<a id="separate-builder-from-object"/>

### 8.1. Separate Builder from Object

One common application of the SRP is separating the builder of a class from the class itself. Often, we have a situation where we want to instantiate a class C from information that was calculated previously (or loaded from in a file or DB). According to SRP and SOC, the building functionality of an instance of C should be separated from C itself.

So this is wrong:

```python
class SomeClass:
    @classmethod
    def build(cls, some_input) -> SomeClass:
        # building an instance of SomeClass from some_input
```

We want a separate class:

```python
class SomeClassBuilder:
    def __init__(self, some_input):
        self.some_input = some_input

    def build(self) -> SomeClass:
        # building logic
        return SomeClass(...)
```

Also, if an instance of SomeClass should never change after it is created, then SomeClass should not have modifier accessors such as:

```python
def set_some_member(self, value):
```

Instead, the constructor of SomeClass should get all the information at once, and be used at the end of the build method of the Builder. Therefore, it is convenient to use [attrs](#6.9.-attrs) to define SomeClass.

Additionally, if the work of the Builder is based not on information calculated previously, but on information that is loaded from a file or DB, then the loading itself should be done by a separate Loader class:

```python
class LoadSomeClass:
    def __init__(self, resource_location):
        ...
    def load(self) -> SomeData:
        ...
```

The sequence is: Instantiating LoadSomeClass with the location of the data (filepath, DB info, etc.), calling its load method to get the loaded data. Then feeding it into the constructor of BuildSomeClass, and calling its build method, to get the instance of SomeClass.

<a id="more"/>

## 9. More

See also: [SOLID](https://en.wikipedia.org/wiki/SOLID)
[The SOLID Principles](https://www.youtube.com/watch?v=RT-npV1JRKE)
[SOLID \- Software Engineers Weekly 22.12.21 presentation](https://docs.google.com/presentation/d/1kzWdZtTHfvxRccQA3aYYpuBIIWrS2WF3/edit?usp=sharing&ouid=107046712976122575333&rtpof=true&sd=true)
[SOLID \- Software Engineers Weekly 22.12.21 recording](https://drive.google.com/file/d/1MUMOLX9EV4gbM3mE2nMVf1oIFDKu9TPY/view?usp=sharing)
TBD: Don't optimize prematurely, use profiler.
