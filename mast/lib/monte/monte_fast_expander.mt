imports
exports (makeBuilder, expand)

def NODE_INFO :Map[Str, Int] := [
    "NounExpr"              => 1,
    "LiteralExpr"           => 1,
    "TempNounExpr"          => 1,
    "SlotExpr"              => 1,
    "MetaContextExpr"       => 0,
    "MetaStateExpr"         => 0,
    "BindingExpr"           => 1,
    "SeqExpr"               => 1,
    "Module"                => 3,
    "NamedArg"              => 2,
    "NamedArgExport"        => 1,
    "MethodCallExpr"        => 4,
    "FunCallExpr"           => 3,
    "SendExpr"              => 4,
    "FunSendExpr"           => 3,
    "GetExpr"               => 2,
    "AndExpr"               => 2,
    "OrExpr"                => 2,
    "BinaryExpr"            => 3,
    "CompareExpr"           => 3,
    "RangeExpr"             => 3,
    "SameExpr"              => 3,
    "MatchBindExpr"         => 2,
    "MismatchExpr"          => 2,
    "PrefixExpr"            => 2,
    "CoerceExpr"            => 2,
    "CurryExpr"             => 3,
    "ExitExpr"              => 2,
    "ForwardExpr"           => 1,
    "DefExpr"               => 3,
    "AssignExpr"            => 2,
    "VerbAssignExpr"        => 3,
    "AugAssignExpr"         => 3,
    "Method"                => 6,
    "To"                    => 6,
    "Matcher"               => 2,
    "Catcher"               => 2,
    "NamedParam"            => 3,
    "NamedParamImport"      => 2,
    "Script"                => 3,
    "FunctionScript"        => 4,
    "FunctionExpr"          => 2,
    "ListExpr"              => 1,
    "ListComprehensionExpr" => 5,
    "MapExprAssoc"          => 2,
    "MapExprExport"         => 1,
    "MapExpr"               => 1,
    "MapComprehensionExpr"  => 6,
    "ForExpr"               => 6,
    "ObjectExpr"            => 5,
    "ParamDesc"             => 2,
    "MessageDesc"           => 4,
    "InterfaceExpr"         => 6,
    "FunctionInterface"     => 6,
    "CatchExpr"             => 3,
    "FinallyExpr"           => 2,
    "TryExpr"               => 3,
    "EscapeExpr"            => 4,
    "SwitchExpr"            => 2,
    "WhenExpr"              => 4,
    "IfExpr"                => 3,
    "WhileExpr"             => 3,
    "HideExpr"              => 1,
    "ValueHoleExpr"         => 1,
    "PatternHoleExpr"       => 1,
    "ValueHolePattern"      => 1,
    "PatternHolePattern"    => 1,
    "FinalPattern"          => 2,
    "BindingPattern"        => 1,
    "SlotPattern"           => 2,
    "IgnorePattern"         => 1,
    "VarPattern"            => 2,
    "BindPattern"           => 2,
    "ListPattern"           => 2,
    "MapPatternAssoc"       => 3,
    "MapPatternImport"      => 2,
    "MapPattern"            => 2,
    "ViaPattern"            => 2,
    "SuchThatPattern"       => 2,
    "SamePattern"           => 2,
    "QuasiText"             => 1,
    "QuasiExprHole"         => 1,
    "QuasiPatternHole"      => 1,
    "QuasiParserExpr"       => 2,
    "QuasiParserPattern"    => 2,
]

def makeBuilder() as DeepFrozen:
    def tree := [].diverge()
    return object fastBuilder:
            to getTree():
                return tree
            match [v ? (NODE_INFO.contains(v)),
                   a :List ? (a.size() == (NODE_INFO[v] + 1)),
                   _]:
                def i := tree.size()
                tree.push(v)
                tree.extend(a)
                object astNodeish extends i:
                    # Just enough to fool the parser.
                    to getNodeName():
                        return v
                    to _conformTo(guard):
                        return i


def findTopNode(tree, ej) as DeepFrozen:
    # Fish around a bit for the last node added.
    def sizes := NODE_INFO.getValues().sort()
    for n in (sizes[0])..(sizes.last()):
        def i := tree.size() - n - 2
        if (NODE_INFO.fetch(tree[i], fn {null}) == n):
            return i
    ej("Could not find a start node, sorry")

def putVerb(verb, fail, span) as DeepFrozen:
    switch (verb):
        match =="get":
            return "put"
        match =="run":
            return "setRun"
        match _:
            fail(["Unsupported verb for assignment", span])


def expand(builder, finalBuilder, fail) as DeepFrozen:
    def tempNames := [].asMap().diverge()
    def nameList := [].diverge()
    def genTemp(name):
        object o {}
        tempNames[o] := name
        return o

    def expandCallAssign(tree, rcvr, pv, margs, right, span):
        def ares_i := tree.size()
        tree.extend(["TempNounExpr", genTemp("ares"), span])
        def fp_i := tree.size()
        tree.extend(["FinalPattern",ares_i, null, span])
        def def_i := tree.size()
        tree.extend(["DefExpr", fp_i, null, right, span])
        return ["SeqExpr",
                span, "out",
                2, "makeList",
                "MethodCallExpr",
                span, "out",
                [], "out",
                2, "concatLists",
                [def_i], "out",
                margs, "expandList",
                pv, "out",
                rcvr, "expand",
                ares_i, "out"]

    def tree := builder.getTree()
    #traceln(`tree $tree`)
    def stack := [findTopNode(tree, fail), "expand"].diverge()
    def outStack := [].diverge()
    while (stack.size() > 0):
        #traceln(`expand$\n$stack$\n$outStack`)
        def op :Str := stack.pop()
        if (op == "out"):
            outStack.push(stack.pop())
        else if (op == "expandList"):
            def items := stack.pop()
            stack.push(items.size())
            stack.push("makeList")
            for item in items:
                stack.push(item)
                stack.push("expand")
        else if (op == "concatLists"):
            def n := stack.pop()
            var fin := []
            for _ in 0..!n:
                fin += outStack.pop()
            outStack.push(fin)
        else if (op == "makeList"):
            def n := stack.pop()
            def l := outStack.slice(outStack.size() - n, outStack.size())
            # XXX add a FlexList.delSlice method?
            for _ in 0..!n:
                outStack.pop()
            outStack.push(l)
        else if (op == "expand"):
            def node :NullOk[Int] := stack.pop()
            if (node == null):
                outStack.push(null)
                continue
            def nodeName := tree[node]
            def siz := NODE_INFO[nodeName]
            def span := tree[node + 1 + siz]
            def getArg(n ? (n < siz)):
                return tree[node + 1 + n]
            def getArgs():
                return tree.slice(node + 1, node + 1 + siz)
            def nameFromNameExpr(n):
                def typ := tree[n]
            if (["BindingExpr", "NounExpr"].contains(nodeName)):
                nameList.push(tree[node + 1])
                outStack.push(node)
            else if (nodeName == "LiteralExpr"):
                outStack.push(node)
            else if (nodeName == "SlotExpr"):
                def name := getArg(0)
                nameList.push(tree[node + 1])
                stack.extend(["MethodCallExpr",
                              span, "out",
                              [], "out",
                              [], "out",
                              "get", "out",
                              "BindingExpr",
                              span, "out",
                              name, "out"])
            else if (nodeName == "MethodCallExpr"):
                def [rcvr, verb, arglist, namedArgs] := getArgs()
                stack.extend(["MethodCallExpr",
                              span, "out",
                              namedArgs, "expandList",
                              arglist, "expandList",
                              verb, "out",
                              rcvr, "expand"])
            else if (nodeName == "NamedArg"):
                def [k, v] := getArgs()
                stack.extend(["NamedArg",
                              span, "out",
                              v, "expand",
                              k, "expand"])
            else if (nodeName == "NamedArgExport"):
                def v := getArg(0)
                def vName := tree[v]
                def k := if (vName == "BindingExpr") {
                    "&&" + tree[v + 2]
                } else if (vName == "SlotExpr") {
                    "&" + tree[v + 2]
                } else {
                    tree[v + 1]
                }
                stack.extend(["NamedArg",
                              span, "out",
                              v, "expand",
                              "NounExpr",
                              span, "out",
                              k, "out"])
            else if (nodeName == "FunCallExpr"):
                def [receiver, fargs, namedArgs] := getArgs()
                stack.extend(["MethodCallExpr",
                              span, "out",
                              namedArgs, "expandList",
                              fargs, "expandList",
                              "run", "out",
                              receiver, "expand"])
            else if (nodeName == "DefExpr"):
                def [patt, exit_, expr] := getArgs()
                #XXX do cycles etc
                stack.extend(["DefExpr",
                              span, "out",
                              expr, "expand",
                              exit_, "expand",
                              patt, "expand"])
            else if (nodeName == "SeqExpr"):
                stack.extend(["SeqExpr", span, "out", getArg(0), "expandList"])
            else if (nodeName == "AssignExpr"):
                def [left :Int, right :Int] := getArgs()
                if (tree[left] == "MethodCallExpr"):
                    def [rcvr, verb, margs, namedArgs] := tree.slice(left + 1, left + 5)
                    def pv := putVerb(verb, fail, span)
                    stack.extend(expandCallAssign(tree, rcvr, pv, margs, right, span))
                else if (tree[left] == "GetExpr"):
                    def [rcvr, margs] := tree.slice(left + 1, left + 3)
                    stack.extend(expandCallAssign(tree, rcvr, "put", margs, right, span))
                else if (tree[left] == "NounExpr"):
                    stack.extend(["AssignExpr",
                                  span, "out",
                                  right, "expand",
                                  left, "expand"])
                else:
                    fail(["Assignment can only be done to nouns and collection elements",
                          span])
            else:
                throw(`No expander for $nodeName`)
        else if (NODE_INFO.contains(op)):
            tree.push(op)
            def n := NODE_INFO[op]
            tree.extend(outStack.slice(outStack.size() - n - 1, outStack.size()))
            for _ in 0..n:
                outStack.pop()
            outStack.push(tree.size() - n - 2)

    if (outStack.size() != 1):
        throw(`outstack shouldn't be $outStack`)


    # reify temporaries
    {
        traceln("reify temporaries")
        def names := nameList.asSet()
        def seen := [].asMap().diverge()
        var i := 0
        var suffix := 0
        while (i < tree.size()) {
            if (!NODE_INFO.contains(tree[i])) {
                throw(`busted: $tree ${tree[i]} $i`)
            } else if (tree[i] == "TempNounExpr") {
                def o := tree[i + 1]
                tree[i] := "NounExpr"
                tree[i + 1] := seen.fetch(o, fn {
                    var noun := null
                    def prefix := tempNames[o]
                    while (true) {
                        suffix += 1
                        def name := `${prefix}_$suffix`
                        if (!names.contains(name)) {
                            seen[o] := name
                            break(name)
                        }
                    }
                })
            }
            i += NODE_INFO[tree[i]] + 2
        }
    }
    traceln("build final ast")
    def buildStack := [outStack.pop(), "build"].diverge()
    while (buildStack.size() > 0):
        #traceln(`build$\n$buildStack$\n$outStack`)
        def op := buildStack.pop()
        if (op == "build"):
            def node := buildStack.pop()
            #traceln(`node $node`)
            def nodeName := tree[node]
            #traceln(`nodename $nodeName`)
            if (nodeName == "LiteralExpr"):
                outStack.push(finalBuilder.LiteralExpr(tree[node + 1], tree[node + 2]))
            else if (nodeName == "TempNounExpr"):
                throw("please how did you get here?")
            else:
                buildStack.push(nodeName)
                def n := NODE_INFO[nodeName]
                for i in (0..n).descending():
                    def o := tree[node + i + 1]
                    if (o =~ _ :Int):
                        buildStack.push(o)
                        buildStack.push("build")
                    else if (o =~ _ :List):
                        buildStack.push(o)
                        buildStack.push("buildList")
                    else:
                        buildStack.push(o)
                        buildStack.push("out")
        else if (op == "buildList"):
            def items := buildStack.pop()
            buildStack.push(items.size())
            buildStack.push("makeList")
            for item in items:
                buildStack.push(item)
                buildStack.push("build")
        else if (op == "makeList"):
            def n := buildStack.pop()
            def l := outStack.slice(outStack.size() - n, outStack.size())
            # XXX add a FlexList.delSlice method?
            for _ in 0..!n:
                outStack.pop()
            outStack.push(l)
        else if (op == "out"):
            outStack.push(buildStack.pop())
        else if (NODE_INFO.contains(op)):
            tree.push(op)
            def n := NODE_INFO[op]
            def arglist := outStack.slice(outStack.size() - n - 1, outStack.size())
            for _ in 0..n:
                outStack.pop()
            outStack.push(M.call(finalBuilder, op, arglist))

    return outStack[0]

