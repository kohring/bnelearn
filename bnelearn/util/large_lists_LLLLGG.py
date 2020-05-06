"""This module contains all possible solutions for the LLLLGG setting to be checked."""
# row, column for ones
subsolutions  = [
    [0, 0],
    [1, 1],
    [2, 2],
    [3, 3],
    [4, 4],
    [5, 5],
    [6, 6],
    [7, 7],
    [8, 8],
    [9, 9],
    [10, 10],
    [11, 11],
    [12, 0],
    [12, 2],
    [13, 0],
    [13, 3],
    [14, 0],
    [14, 4],
    [15, 0],
    [15, 5],
    [16, 0],
    [16, 6],
    [17, 0],
    [17, 9],
    [18, 0],
    [18, 10],
    [19, 1],
    [19, 3],
    [20, 1],
    [20, 4],
    [21, 1],
    [21, 5],
    [22, 1],
    [22, 6],
    [23, 1],
    [23, 7],
    [24, 1],
    [24, 9],
    [25, 2],
    [25, 4],
    [26, 2],
    [26, 5],
    [27, 2],
    [27, 6],
    [28, 2],
    [28, 7],
    [29, 2],
    [29, 9],
    [30, 2],
    [30, 11],
    [31, 3],
    [31, 5],
    [32, 3],
    [32, 6],
    [33, 3],
    [33, 7],
    [34, 3],
    [34, 11],
    [35, 4],
    [35, 6],
    [36, 4],
    [36, 7],
    [37, 4],
    [37, 8],
    [38, 4],
    [38, 11],
    [39, 5],
    [39, 7],
    [40, 5],
    [40, 8],
    [41, 6],
    [41, 8],
    [42, 6],
    [42, 10],
    [43, 7],
    [43, 10],
    [44, 0],
    [44, 2],
    [44, 4],
    [45, 0],
    [45, 2],
    [45, 5],
    [46, 0],
    [46, 2],
    [46, 6],
    [47, 0],
    [47, 2],
    [47, 9],
    [48, 0],
    [48, 3],
    [48, 5],
    [49, 0],
    [49, 3],
    [49, 6],
    [50, 0],
    [50, 4],
    [50, 6],
    [51, 0],
    [51, 6],
    [51, 10],
    [52, 1],
    [52, 3],
    [52, 5],
    [53, 1],
    [53, 3],
    [53, 6],
    [54, 1],
    [54, 3],
    [54, 7],
    [55, 1],
    [55, 4],
    [55, 6],
    [56, 1],
    [56, 4],
    [56, 7],
    [57, 1],
    [57, 5],
    [57, 7],
    [58, 2],
    [58, 4],
    [58, 6],
    [59, 2],
    [59, 4],
    [59, 7],
    [60, 2],
    [60, 4],
    [60, 11],
    [61, 2],
    [61, 5],
    [61, 7],
    [62, 3],
    [62, 5],
    [62, 7],
    [63, 4],
    [63, 6],
    [63, 8],
    [64, 0],
    [64, 2],
    [64, 4],
    [64, 6],
    [65, 1],
    [65, 3],
    [65, 5],
    [65 ,7]
    ]

solutions_sparse = [
    # 4 local bidders win
    [0, 2, 4, 6], 	# AB CD EF GH
    [1, 3, 5, 7], 	# BC DE FG HA
    # a global bidder wins (2 possibilities for each global bundle)
    [4, 6, 8, 99],     # EF GH ABCD
    [0, 2, 9, 99],    	# AB CD EFGH
    [0, 6, 10, 99],   	# AB GH CDEF
    [2, 4, 11, 99],    # CD EF GHAB
    [5, 8, 99, 99],        # FG ABCD
    [1, 9, 99, 99],		# BC EFGH
    [7, 10, 99, 99],       # HA CDEF
    [3, 11, 99, 99],       # DE GHAB
    # 3 locals win. This implies that 2 locals have adjacent bundles, and one doesn't.
    # there are 8 possibilities (choose bundle that has no adjacent bundles, the rest is determined)
    [0, 2, 5, 99],    	# AB CD FG
    [2, 4, 7, 99],     # CD EF HA
    [1, 4, 6, 99],		# BC EF GH
    [0, 3, 6, 99],    	# AB DE GH
    [0, 3, 5, 99],    	# AB DE FG
    [2, 5, 7, 99],     # CD FG HA
    [1, 3, 6, 99],		# BC DE GH
    [1, 4, 7, 99],		# BC EF HA
    ]

solutions_non_sparse = [
    # 4 local bidders win
    [1,0,1,0, 1,0,1,0, 0,0,0,0], # AB CD EF GH
    [0,1,0,1, 0,1,0,1, 0,0,0,0], # BC DE FG HA
    # a global bidder wins (2 possibilities for each global bundle)
    [0,0,0,0, 1,0,1,0, 1,0,0,0], # EF GH ABCD
    [1,0,1,0, 0,0,0,0, 0,1,0,0], # AB CD EFGH
    [1,0,0,0, 0,0,1,0, 0,0,1,0], # AB GH CDEF
    [0,0,1,0, 1,0,0,0, 0,0,0,1], # CD EF GHAB
    [0,0,0,0, 0,1,0,0, 1,0,0,0], # FG ABCD
    [0,1,0,0, 0,0,0,0, 0,1,0,0], # BC EFGH
    [0,0,0,0, 0,0,0,1, 0,0,1,0], # HA CDEF
    [0,0,0,1, 0,0,0,0, 0,0,0,1], # DE GHAB
    # 3 locals win. This implies that 2 locals have adjacent bundles, and one doesn't.
    # there are 8 possibilities (choose bundle that has no adjacent bundles, the rest is determined)
    [1,0,1,0, 0,1,0,0, 0,0,0,0], # AB CD FG
    [0,0,1,0, 1,0,0,1, 0,0,0,0], # CD EF HA
    [0,1,0,0, 1,0,1,0, 0,0,0,0], # BC EF GH
    [1,0,0,1, 0,0,1,0, 0,0,0,0], # AB DE GH
    [1,0,0,1, 0,1,0,0, 0,0,0,0], # AB DE FG
    [0,0,1,0, 0,1,0,1, 0,0,0,0], # CD FG HA
    [0,1,0,1, 0,0,1,0, 0,0,0,0], # BC DE GH
    [0,1,0,0, 1,0,0,1, 0,0,0,0], # BC EF HA
    ]
