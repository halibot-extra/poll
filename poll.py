import random
from halibot import CommandModule, Message, HalConfigurer
from halibot import AsArgs
import uuid

def get_randstring():
	return uuid.uuid4().hex[:6]

def plural(n):
	return "s" if n != 1 else ""

class Poll:
	def __init__(self, choices=[], question="", originmsg=None):
		self.pollid = get_randstring()
		# TODO: use list instead?
		self.responses = {i:0 for i in range(1, len(choices)+1)}
		self.voted = []
		self.choices = choices
		if originmsg:
			self.originmsg = originmsg
			self.origin = originmsg.origin
			self.author = originmsg.author
	
	def results(self):
		ret = []
		for i in self.responses.items():
			ret.append((self.choices[i[0]-1], i[1]))

		ret = sorted(ret, key=lambda x: x[1], reverse=True)

		return ret

class PollModule(CommandModule):

	class Configurer(HalConfigurer):
		def configure(self):
			self.optionInt('timeout', prompt="Poll Timeout", default=600)

	def init(self):
		self.commands = {
			"poll": self.poll_,
			"prespond": self.respond_,
			"pvote": self.respond_,
			"pcreate": self.create_,
			"pend": self.end_
		}

		self.polls = {}

	# Clean up any non-timed out polls just to be safe
	def shutdown(self):
		for p in self.polls.items():
			try:
				p[1].callback.cancel()
			except:
				pass

	def poll_(self, args, msg=None):
		sub, rest = args.split(" ",1)
		if sub in ["create", "new"]:
			self.create_(rest, msg=msg)
		elif sub in ["end", "endpoll"]:
			self.end_(rest, msg=msg)
		elif sub in ["respond", "resp", "vote"]:
			self.respond_(rest, msg=msg)
		elif sub in self.polls.keys():
			self.respond_(sub + " " + rest, msg=msg)
		else:
			self.reply(msg, body="Unknown subcommand")

	# Pattern: <question> - item 1, item 2, item 3
	def create_(self, args, msg=None):
		question = ""
		q = args.split(" - ", 1)
		if len(q) == 2:
			question = q.pop(0)

		choices = q[0].split(", ")
		if len(choices) <= 1:
			self.reply(msg, body="Polls need more than one option")
			return

		p = Poll(choices=choices, question=question, originmsg=msg)
		self.polls[p.pollid] = p

		# TODO: Config this
		p.callback = self.eventloop.call_later(self.config.get("timeout", 600), self.endpoll, p)

		self.reply(msg, body="Poll '{0}' created! PM your response with !poll respond {0} <num 1-{1}>".format(p.pollid, len(p.choices)))
		self.reply(msg, body="Options are - " + ", ".join(["{}: {}".format(i, p.choices[i-1]) for i in p.responses.keys()]))

	# Pattern: <pollid>
	def end_(self, args, msg=None):
		p = self.polls.get(args, None)
		if not p:
			self.reply(msg, body="Poll '{}' not found!".format(args))
			return
		if p.origin != msg.origin:
			self.reply(msg, body="Please close this poll in the channel it was opened in")
			return
		# TODO: use identity?
		if p.author != msg.author:
			self.reply(msg, body="Only the poll creator can close this poll")
		# End the callback since we don't need to timeout now
		p.callback.cancel()
		self.endpoll(p)

	# End the poll and send the results. Can be called by timeout.
	def endpoll(self, poll):
		self.polls.pop(poll.pollid)
		msg = Message(target=poll.origin)

		results = poll.results()
		if not results:
			msg.body = "Poll ended with no votes"	
			self.send_to(msg, [msg.target])
			return
		# Remove choices with lower votes
		results = [i for i in results if i[1] == results[0][1]]

		if len(results) == 1:
			msg.body = "Results are in: Winner is '{}' with {} vote{}".format(*results[0], plural(results[0][1]))
		else:
			tstr = ", and ".join(['{}'.format(i[0]) for i in results])
			msg.body = "There is a tie between {0}, for {1} vote{2}".format(tstr, results[0][1], plural(results[0][1]))
		self.send_to(msg, [msg.target])

	# Pattern: <pollid> <response number>
	def respond_(self, args, msg=None):
		ls = args.split(" ")
		if len(ls) != 2:
			self.reply(msg, body="Please respond with the poll id, followed by a response number")
			return

		pollid, response = ls

		p = self.polls.get(pollid)
		if not p:
			self.reply(msg, body="Invalid poll id")
			return

		try:
			response = int(response)
		except:
			self.reply(msg, body="Response must be a number")
			return

		if 0 >= response or response > len(p.choices):
			self.reply(msg, body="There are only {0} choices, please select 1-{0}".format(len(p.choices)))
			return

		# TODO: Use identity
		if msg.author in p.voted:
			self.reply(msg, body="You already voted in this poll!")
			return

		p.voted.append(msg.author)
		p.responses[response] += 1
		self.reply(msg, body="Thanks for the vote :)")
