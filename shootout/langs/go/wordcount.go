// wordcount kernel (Go): port of tasks/wordcount/ref.c.
package main

func isSpace(c byte) bool {
	return c == ' ' || (c >= '\t' && c <= '\r') // space, \t \n \v \f \r
}

func wordcount(buf []byte) uint64 {
	var words uint64
	inWord := false
	for _, c := range buf {
		if isSpace(c) {
			inWord = false
		} else if !inWord {
			inWord = true
			words++
		}
	}
	return words
}

func run(data []byte) uint64 { return wordcount(data) }
func digest() uint64         { return 0 }
